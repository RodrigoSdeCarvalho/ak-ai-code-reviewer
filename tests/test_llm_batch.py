"""BatchClient against a fake Message Batches SDK: submission, out-of-order results, row mapping, resume."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types.messages import MessageBatchIndividualResponse

from aireview.llm import batch as batch_module
from aireview.llm.base import LLMRequest, LLMResponse
from aireview.llm.batch import BatchClient
from aireview.llm.cassette import BudgetExceeded, BudgetTracker, CassetteConflict, CassetteStore, ReplayClient
from aireview.models import ReviewOutput
from aireview.settings import cost_usd


def make_request(user: str = "diff") -> LLMRequest:
    return LLMRequest(
        role="reviewer",
        model="claude-sonnet-5-5",
        system="You review code.",
        user=user,
        output_schema=ReviewOutput.model_json_schema(),
    )


def message_dict(text: str, model: str = "claude-sonnet-5-5", stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1000, "output_tokens": 100},
    }


def row(custom_id: str, result: dict[str, Any]) -> MessageBatchIndividualResponse:
    return MessageBatchIndividualResponse.model_validate({"custom_id": custom_id, "result": result})


def succeeded(custom_id: str, text: str, **kw: Any) -> MessageBatchIndividualResponse:
    return row(custom_id, {"type": "succeeded", "message": message_dict(text, **kw)})


class FakeBatches:
    def __init__(self, statuses: list[str] | None = None) -> None:
        self.statuses = statuses or ["in_progress", "ended"]
        self.created: list[list[dict[str, Any]]] = []
        self.rows: list[MessageBatchIndividualResponse] = []
        self.canceled: list[str] = []
        self.retrieves = 0

    def create(self, *, requests: list[dict[str, Any]]) -> SimpleNamespace:
        self.created.append(list(requests))
        return SimpleNamespace(id=f"msgbatch_{len(self.created)}", processing_status="in_progress")

    def retrieve(self, batch_id: str) -> SimpleNamespace:
        status = self.statuses[min(self.retrieves, len(self.statuses) - 1)]
        self.retrieves += 1
        return SimpleNamespace(id=batch_id, processing_status=status)

    def results(self, batch_id: str) -> list[MessageBatchIndividualResponse]:
        return list(self.rows)

    def cancel(self, batch_id: str) -> SimpleNamespace:
        self.canceled.append(batch_id)
        return SimpleNamespace(id=batch_id, processing_status="canceling")


def fake_sdk(batches: FakeBatches) -> SimpleNamespace:
    return SimpleNamespace(messages=SimpleNamespace(batches=batches))


@pytest.fixture(autouse=True)
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """`sleep` advances a fake monotonic clock instead of waiting."""
    now = [0.0]
    monkeypatch.setattr(batch_module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(batch_module.time, "sleep", lambda s: now.__setitem__(0, now[0] + s))
    return now


def test_one_batch_out_of_order_results_mapped_and_stored(tmp_path: Path) -> None:
    reqs = [make_request(user=f"u{i}") for i in range(5)]
    keys = [r.key() for r in reqs]
    batches = FakeBatches()
    batches.rows = [
        succeeded(keys[3], '{"i": 3}'),
        row(
            keys[1],
            {"type": "errored", "error": {"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}},
        ),
        succeeded(keys[0], '{"i": 0}'),
        row(keys[2], {"type": "expired"}),
        row(keys[4], {"type": "canceled"}),
    ]
    store = CassetteStore(tmp_path)
    budget = BudgetTracker(10.0)
    client = BatchClient(store, budget=budget, poll_s=0, client=fake_sdk(batches))
    out = client.complete_many(reqs)

    assert len(batches.created) == 1
    sent = batches.created[0]
    assert [r["custom_id"] for r in sent] == keys
    params = sent[0]["params"]
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert params["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in params

    assert out[0].parsed == {"i": 0} and out[3].parsed == {"i": 3}
    assert out[0].batch and out[0].usage.latency_ms is None and out[0].request_id == "msgbatch_1"
    assert out[0].usage.cost_usd == pytest.approx(cost_usd("claude-sonnet-5-5", 1000, 100, batch=True))
    assert out[1].error_class == "api_error" and "overloaded_error" in out[1].error
    assert out[2].error_class == "timeout"
    assert out[4].error_class == "api_error" and "canceled" in out[4].error
    assert budget.spent == pytest.approx(2 * cost_usd("claude-sonnet-5-5", 1000, 100, batch=True))

    assert store.path_for(reqs[0]).exists() and store.path_for(reqs[3]).exists()
    for i in (1, 2, 4):
        assert not store.path_for(reqs[i]).exists()


def test_missing_row_is_an_error(tmp_path: Path) -> None:
    req = make_request()
    client = BatchClient(CassetteStore(tmp_path), poll_s=0, client=fake_sdk(FakeBatches()))
    resp = client.complete(req)
    assert resp.error_class == "api_error" and "no result" in resp.error


def test_resume_skips_stored_requests_only_when_asked(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    done, todo = make_request(user="done"), make_request(user="todo")
    store.put(done, LLMResponse(parsed={"old": True}))

    batches = FakeBatches()
    batches.rows = [succeeded(todo.key(), '{"new": 1}')]
    out = BatchClient(store, poll_s=0, resume=True, client=fake_sdk(batches)).complete_many([done, todo])
    assert [r["custom_id"] for r in batches.created[0]] == [todo.key()]
    assert out[0].from_cache and out[0].parsed == {"old": True}
    assert out[1].parsed == {"new": 1} and not out[1].from_cache

    # Without resume an existing cassette is never overwritten: nothing is submitted or paid for.
    batches2 = FakeBatches()
    with pytest.raises(CassetteConflict):
        BatchClient(store, poll_s=0, client=fake_sdk(batches2)).complete_many([done])
    assert batches2.created == []
    assert json.loads(store.path_for(done).read_text(encoding="utf-8"))["response"]["parsed"] == {"old": True}


def test_all_cached_with_resume_submits_nothing(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    req = make_request()
    store.put(req, LLMResponse(parsed={"x": 1}))
    batches = FakeBatches()
    assert BatchClient(store, resume=True, client=fake_sdk(batches)).complete(req).parsed == {"x": 1}
    assert batches.created == []


def test_duplicate_requests_share_one_row(tmp_path: Path) -> None:
    req = make_request()
    batches = FakeBatches()
    batches.rows = [succeeded(req.key(), '{"a": 1}')]
    out = BatchClient(CassetteStore(tmp_path), poll_s=0, client=fake_sdk(batches)).complete_many([req, req])
    assert len(batches.created[0]) == 1
    assert [r.parsed for r in out] == [{"a": 1}, {"a": 1}]


def test_wait_timeout_cancels_and_reports(tmp_path: Path) -> None:
    batches = FakeBatches(statuses=["in_progress"])
    client = BatchClient(CassetteStore(tmp_path), poll_s=10, max_wait_s=25, cancel_wait_s=15, client=fake_sdk(batches))
    resp = client.complete(make_request())
    assert resp.error_class == "timeout" and "msgbatch_1" in resp.error
    assert batches.canceled == ["msgbatch_1"]
    assert batches.retrieves == 3 + 2  # t=0, 10, 20 (25 s limit), then t=20, 30 waiting for the cancel


def test_cancel_after_wait_limit_keeps_finished_rows(tmp_path: Path) -> None:
    """Rows that finished before the cancel are billed: they are charged to the budget and stored."""
    done, late = make_request(user="done"), make_request(user="late")
    batches = FakeBatches(statuses=["in_progress", "in_progress", "in_progress", "canceling", "ended"])
    batches.rows = [succeeded(done.key(), '{"ok": 1}'), row(late.key(), {"type": "canceled"})]
    store, budget = CassetteStore(tmp_path), BudgetTracker(10.0)
    client = BatchClient(store, budget=budget, poll_s=10, max_wait_s=25, client=fake_sdk(batches))
    out = client.complete_many([done, late])
    assert batches.canceled == ["msgbatch_1"]
    assert out[0].parsed == {"ok": 1} and store.exists(done)
    assert out[1].error_class == "timeout" and not store.exists(late)
    assert budget.spent == pytest.approx(cost_usd("claude-sonnet-5-5", 1000, 100, batch=True))


def test_transient_poll_errors_are_retried(tmp_path: Path) -> None:
    req = make_request()
    batches = FakeBatches()
    batches.rows = [succeeded(req.key(), '{"a": 1}')]
    real_retrieve, failures = batches.retrieve, [2]

    def flaky_retrieve(batch_id: str) -> SimpleNamespace:
        if failures[0]:
            failures[0] -= 1
            raise anthropic.APIConnectionError(request=httpx2.Request("GET", "https://api.anthropic.com"))
        return real_retrieve(batch_id)

    batches.retrieve = flaky_retrieve  # type: ignore[method-assign]
    out = BatchClient(CassetteStore(tmp_path), poll_s=0, client=fake_sdk(batches)).complete(req)
    assert out.parsed == {"a": 1} and failures == [0]


def test_model_outcome_failures_are_recorded_and_replayed(tmp_path: Path) -> None:
    """A truncated row is the model's outcome: stored, so replay gives truncated again, not cassette_missing."""
    req = make_request()
    batches = FakeBatches()
    batches.rows = [succeeded(req.key(), '{"findings": [', stop_reason="max_tokens")]
    store = CassetteStore(tmp_path)
    recorded = BatchClient(store, poll_s=0, client=fake_sdk(batches)).complete(req)
    replayed = ReplayClient(store).complete(req)
    assert recorded.error_class == replayed.error_class == "truncated"
    assert replayed.usage.cost_usd == recorded.usage.cost_usd > 0


def test_budget_checked_before_submission(tmp_path: Path) -> None:
    budget = BudgetTracker(1.0)
    budget.add(1.0)
    batches = FakeBatches()
    with pytest.raises(BudgetExceeded):
        BatchClient(CassetteStore(tmp_path), budget=budget, client=fake_sdk(batches)).complete(make_request())
    assert batches.created == []
