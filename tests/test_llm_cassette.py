"""Cassette store format and the replay/record contract: replay never calls out, record never reads the cache."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from aireview.llm.base import LLMRequest, LLMResponse
from aireview.llm.cassette import (
    BudgetExceeded,
    BudgetTracker,
    CassetteConflict,
    CassetteStore,
    RecordingClient,
    ReplayClient,
    make_client,
)
from aireview.models import ReviewOutput, Usage


def make_request(user: str = "diff --git a/x.py b/x.py", **kw: object) -> LLMRequest:
    return LLMRequest(
        role="reviewer",
        model="claude-sonnet-5-5",
        system="You review code.",
        user=user,
        output_schema=ReviewOutput.model_json_schema(),
        prompt_version="v1",
        **kw,
    )


class CountingClient:
    """Fake inner client: counts calls, answers with the user text, optionally fails."""

    concurrency = 3

    def __init__(self, error_class: str | None = None, cost: float = 0.01) -> None:
        self.calls = 0
        self.error_class = error_class
        self.cost = cost
        self._lock = threading.Lock()

    def complete(self, request: LLMRequest) -> LLMResponse:
        with self._lock:
            self.calls += 1
        if self.error_class:
            return LLMResponse(error="boom", error_class=self.error_class)
        return LLMResponse(parsed={"user": request.user}, usage=Usage(cost_usd=self.cost, latency_ms=10))

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        return [self.complete(r) for r in requests]


def test_store_layout_and_file_format(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    req = make_request(user="héllo", sample=2, effort="high")
    store.put(req, LLMResponse(parsed={"findings": []}, raw_text='{"findings": []}', from_cache=True))

    path = store.path_for(req)
    assert path == tmp_path / "reviewer" / "claude-sonnet-5-5" / f"{req.key()}.json"
    raw = path.read_bytes()
    assert b"\r\n" not in raw and "héllo".encode() not in raw  # user text is hashed, not stored
    data = json.loads(raw.decode("utf-8"))
    assert set(data) == {"request_meta", "response", "recorded_at"}
    meta = data["request_meta"]
    assert meta["key"] == req.key() and meta["sample"] == 2 and meta["effort"] == "high"
    assert meta["user_chars"] == 5 and len(meta["user_sha256"]) == 64
    assert data["recorded_at"].endswith("+00:00")
    assert data["response"]["from_cache"] is False
    assert raw.decode("utf-8") == json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    assert list(path.parent.glob("*.tmp")) == []

    got = store.get(req)
    assert got is not None and got.from_cache and got.parsed == {"findings": []}


def test_get_missing_returns_none_and_key_mismatch_raises(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    a, b = make_request(user="a"), make_request(user="b")
    assert store.get(a) is None
    store.put(a, LLMResponse(parsed={}))
    store.path_for(b).write_bytes(store.path_for(a).read_bytes())
    with pytest.raises(ValueError, match="holds key"):
        store.get(b)


def test_replay_never_calls_a_model(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    hit, miss = make_request(user="hit"), make_request(user="miss")
    store.put(hit, LLMResponse(parsed={"user": "hit"}))
    client = ReplayClient(store)
    out = client.complete_many([hit, miss])
    assert out[0].parsed == {"user": "hit"} and out[0].from_cache
    assert out[1].error_class == "cassette_missing" and f"{miss.role}/{miss.model}/{miss.key()}.json" in out[1].error
    assert out[1].parsed is None


def test_record_never_overwrites_an_existing_cassette(tmp_path: Path) -> None:
    """Write-once: a second record of the same key would change what the first run replays."""
    store = CassetteStore(tmp_path)
    req = make_request()
    store.put(req, LLMResponse(parsed={"first": True}))
    inner = CountingClient()
    with pytest.raises(CassetteConflict):
        RecordingClient(inner, store).complete(req)
    assert inner.calls == 0
    assert store.get(req).parsed == {"first": True}


def test_independent_samples_get_their_own_cassettes(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    first, second = make_request(sample=0), make_request(sample=3)  # --sample-offset 3
    inner = CountingClient()
    RecordingClient(inner, store).complete_many([first])
    RecordingClient(inner, store).complete_many([second])
    assert inner.calls == 2 and store.exists(first) and store.exists(second)
    assert store.path_for(first) != store.path_for(second)


def test_record_resume_reuses_existing_cassette(tmp_path: Path) -> None:
    store = CassetteStore(tmp_path)
    old, new = make_request(user="old"), make_request(user="new")
    store.put(old, LLMResponse(parsed={"stale": True}))
    inner = CountingClient()
    out = RecordingClient(inner, store, resume=True).complete_many([old, new])
    assert inner.calls == 1
    assert out[0].from_cache and out[0].parsed == {"stale": True}
    assert out[1].parsed == {"user": "new"}


@pytest.mark.parametrize("error_class", ["api_error", "timeout"])
def test_record_does_not_store_transport_failures(tmp_path: Path, error_class: str) -> None:
    store = CassetteStore(tmp_path)
    req = make_request()
    resp = RecordingClient(CountingClient(error_class=error_class), store).complete(req)
    assert resp.error_class == error_class
    assert not store.path_for(req).exists()


@pytest.mark.parametrize("error_class", ["truncated", "refused", "schema_error", "model_mismatch"])
def test_record_stores_model_outcomes_and_replay_reproduces_them(tmp_path: Path, error_class: str) -> None:
    """A truncation/refusal is what the model did: replay must give the same status, not cassette_missing."""
    store = CassetteStore(tmp_path)
    req = make_request()
    recorded = RecordingClient(CountingClient(error_class=error_class), store).complete(req)
    replayed = ReplayClient(store).complete(req)
    assert replayed.error_class == recorded.error_class == error_class
    assert replayed.error == recorded.error and replayed.from_cache


def test_record_complete_many_keeps_order(tmp_path: Path) -> None:
    reqs = [make_request(user=f"u{i}") for i in range(12)]
    out = RecordingClient(CountingClient(), CassetteStore(tmp_path)).complete_many(reqs)
    assert [r.parsed["user"] for r in out] == [f"u{i}" for i in range(12)]


def test_budget_tracker() -> None:
    budget = BudgetTracker(0.05)
    budget.add(0.02)
    budget.check()
    budget.add(0.03)
    with pytest.raises(BudgetExceeded):
        budget.check()


def test_record_stops_when_budget_is_spent(tmp_path: Path) -> None:
    budget = BudgetTracker(0.025)
    inner = CountingClient(cost=0.01)
    client = RecordingClient(inner, CassetteStore(tmp_path), budget=budget)
    for i in range(3):
        client.complete(make_request(user=f"u{i}"))
    with pytest.raises(BudgetExceeded):
        client.complete(make_request(user="u3"))
    assert inner.calls == 3 and budget.spent == pytest.approx(0.03)


def test_make_client_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = CassetteStore(tmp_path)
    assert isinstance(make_client("replay", store=store), ReplayClient)
    with pytest.raises(ValueError, match="unknown mode"):
        make_client("live", store=store)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match=r"\.env\.example"):
        make_client("record", store=store)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    from aireview.llm.anthropic_client import AnthropicClient
    from aireview.llm.batch import BatchClient

    recording = make_client("record", store=store, resume=True)
    assert isinstance(recording, RecordingClient) and recording.resume
    assert isinstance(recording.inner, AnthropicClient)
    batch = make_client("record", store=store, batch=True, resume=True)
    assert isinstance(batch, BatchClient) and batch.resume and batch.store is store
