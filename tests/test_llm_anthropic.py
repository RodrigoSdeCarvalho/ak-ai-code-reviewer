"""AnthropicClient against a fake SDK: params, response mapping, retries, timeouts. No network."""

from __future__ import annotations

import json
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types import Message

from aireview.llm import anthropic_client as ac
from aireview.llm.anthropic_client import AnthropicClient, build_params, message_to_response
from aireview.llm.base import LLMRequest
from aireview.models import ReviewOutput
from aireview.settings import cost_usd

_HTTP_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def make_request(**overrides: Any) -> LLMRequest:
    fields: dict[str, Any] = {
        "role": "reviewer",
        "model": "claude-sonnet-5-5",
        "system": "You review code.",
        "user": "diff --git a/x.py b/x.py",
        "output_schema": ReviewOutput.model_json_schema(),
        "max_tokens": 4000,
    }
    fields.update(overrides)
    return LLMRequest(**fields)


def make_message(
    text: str | None = '{"findings": []}',
    *,
    model: str = "claude-sonnet-5-5",
    stop_reason: str = "end_turn",
    thinking: bool = False,
    request_id: str | None = "req_1",
) -> Message:
    content: list[dict[str, Any]] = []
    if thinking:
        content.append({"type": "thinking", "thinking": "hmm", "signature": "sig"})
    if text is not None:
        content.append({"type": "text", "text": text})
    msg = Message.model_validate(
        {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 200,
                "cache_read_input_tokens": 500,
                "cache_creation_input_tokens": 100,
            },
        }
    )
    msg._request_id = request_id
    return msg


def status_error(cls: type[anthropic.APIStatusError], code: int, headers: dict[str, str] | None = None):
    response = httpx2.Response(code, request=_HTTP_REQUEST, headers=headers or {})
    return cls(f"status {code}", response=response, body=None)


class FakeMessages:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Message:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeSDK:
    def __init__(self, outcomes: list[Any]) -> None:
        self.messages = FakeMessages(outcomes)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(ac.time, "sleep", slept.append)
    return slept


def client_for(outcomes: list[Any], **kwargs: Any) -> tuple[AnthropicClient, FakeSDK]:
    sdk = FakeSDK(outcomes)
    return AnthropicClient(client=sdk, **kwargs), sdk


def test_transformed_review_schema_shape() -> None:
    schema = build_params(make_request())["output_config"]["format"]["schema"]
    finding = schema["$defs"]["Finding"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["findings"]["items"] == {"$ref": "#/$defs/Finding"}
    assert finding["additionalProperties"] is False
    line, confidence = finding["properties"]["line"], finding["properties"]["confidence"]
    assert "minimum" not in line and "{minimum: 1}" in line["description"]
    assert "maximum" not in confidence and "minimum" not in confidence
    assert "maximum: 1" in confidence["description"]
    assert finding["properties"]["end_line"]["anyOf"][1] == {"type": "null"}
    assert schema["$defs"]["Severity"]["enum"] == ["critical", "high", "medium", "low"]


def test_params_have_cached_system_schema_and_no_sampling_knobs() -> None:
    params = build_params(make_request(effort="high"))
    assert params["system"] == [{"type": "text", "text": "You review code.", "cache_control": {"type": "ephemeral"}}]
    assert params["messages"] == [{"role": "user", "content": "diff --git a/x.py b/x.py"}]
    assert params["output_config"]["effort"] == "high"
    assert params["output_config"]["format"]["type"] == "json_schema"
    for forbidden in ("temperature", "top_p", "top_k", "thinking"):
        assert forbidden not in params
    assert "effort" not in build_params(make_request())["output_config"]


def test_success_maps_usage_cost_and_skips_thinking_blocks() -> None:
    client, sdk = client_for([make_message('{"findings": [1]}', thinking=True)])
    resp = client.complete(make_request())
    assert resp.error is None and resp.parsed == {"findings": [1]}
    assert resp.served_model == "claude-sonnet-5-5" and resp.request_id == "req_1"
    assert resp.attempts == 1 and resp.usage.latency_ms is not None
    assert (resp.usage.cache_read_input_tokens, resp.usage.cache_creation_input_tokens) == (500, 100)
    assert resp.usage.cost_usd == pytest.approx(cost_usd("claude-sonnet-5-5", 1000, 200, 500, 100))
    assert sdk.messages.calls[0]["timeout"] > 0
    assert "temperature" not in sdk.messages.calls[0]


@pytest.mark.parametrize(
    ("message", "error_class"),
    [
        (make_message('{"findings": [', stop_reason="max_tokens"), "truncated"),
        (make_message("I can't help with that.", stop_reason="refusal"), "refused"),
        (make_message("not json"), "schema_error"),
        (make_message("[1, 2]"), "schema_error"),
        (make_message(None), "schema_error"),
        (make_message(model="claude-haiku-5-5"), "model_mismatch"),
    ],
)
def test_unusable_outputs_are_classified(message: Message, error_class: str) -> None:
    client, _ = client_for([message])
    resp = client.complete(make_request())
    assert resp.error_class == error_class and resp.error
    assert resp.parsed is None
    assert resp.usage.output_tokens == 200  # spend is still recorded


def test_truncated_keeps_raw_text() -> None:
    client, _ = client_for([make_message('{"findings": [', stop_reason="max_tokens")])
    assert client.complete(make_request()).raw_text == '{"findings": ['


def test_dated_snapshot_is_accepted() -> None:
    client, _ = client_for([make_message(model="claude-sonnet-5-5-20261001")])
    resp = client.complete(make_request())
    assert resp.error is None and resp.served_model == "claude-sonnet-5-5-20261001"


def test_retries_transient_errors_then_succeeds(no_sleep: list[float]) -> None:
    outcomes = [
        status_error(anthropic.RateLimitError, 429, {"retry-after": "7"}),
        status_error(anthropic.InternalServerError, 500),
        status_error(anthropic.OverloadedError, 529),
        anthropic.APIConnectionError(request=_HTTP_REQUEST),
        make_message(),
    ]
    client, sdk = client_for(outcomes, backoff_base_s=1.0)
    resp = client.complete(make_request())
    assert resp.error is None and resp.attempts == 5
    assert len(sdk.messages.calls) == 5 and len(no_sleep) == 4
    assert no_sleep[0] >= 7  # retry-after honoured
    assert all(0 < s <= 60 for s in no_sleep)


def test_does_not_retry_4xx() -> None:
    client, sdk = client_for([status_error(anthropic.BadRequestError, 400)])
    resp = client.complete(make_request())
    assert resp.error_class == "api_error" and resp.attempts == 1
    assert len(sdk.messages.calls) == 1


def test_gives_up_after_max_attempts() -> None:
    client, sdk = client_for([status_error(anthropic.InternalServerError, 500)] * 3, max_attempts=3)
    resp = client.complete(make_request())
    assert resp.error_class == "api_error" and resp.attempts == 3
    assert "InternalServerError" in resp.error
    assert len(sdk.messages.calls) == 3


def test_wall_clock_ceiling_returns_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = iter([0.0, 0.0, 0.0, 400.0, 400.0])
    monkeypatch.setattr(ac.time, "monotonic", lambda: next(clock))
    client, sdk = client_for([anthropic.APITimeoutError(request=_HTTP_REQUEST)], timeout_s=300)
    resp = client.complete(make_request())
    assert resp.error_class == "timeout" and resp.attempts == 1
    assert sdk.messages.calls[0]["timeout"] == 300


def test_backoff_past_deadline_returns_timeout() -> None:
    client, sdk = client_for([status_error(anthropic.RateLimitError, 429, {"retry-after": "50"})], timeout_s=10)
    resp = client.complete(make_request())
    assert resp.error_class == "timeout"
    assert len(sdk.messages.calls) == 1


def test_latency_is_final_attempt_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # deadline, remaining, started(1st), deadline check (backoff), remaining, started(2nd), end
    clock = iter([0.0, 0.0, 0.0, 30.0, 30.0, 30.0, 32.5])
    monkeypatch.setattr(ac.time, "monotonic", lambda: next(clock))
    client, _ = client_for([anthropic.APIConnectionError(request=_HTTP_REQUEST), make_message()])
    resp = client.complete(make_request())
    assert resp.attempts == 2 and resp.usage.latency_ms == 2500


def test_unpriced_model_fails_before_any_call() -> None:
    client, sdk = client_for([make_message(model="claude-unknown")])
    with pytest.raises(KeyError):
        client.complete(make_request(model="claude-unknown"))
    assert sdk.messages.calls == []


def test_complete_many_preserves_order() -> None:
    class EchoMessages:
        def create(self, **kwargs: Any) -> Message:
            user = kwargs["messages"][0]["content"]
            return make_message(json.dumps({"user": user}))

    sdk = FakeSDK([])
    sdk.messages = EchoMessages()  # type: ignore[assignment]
    client = AnthropicClient(client=sdk, concurrency=3)
    reqs = [make_request(user=f"u{i}") for i in range(10)]
    assert [r.parsed["user"] for r in client.complete_many(reqs)] == [f"u{i}" for i in range(10)]
    assert client.complete_many([]) == []


def test_message_to_response_batch_cost_is_discounted() -> None:
    resp = message_to_response(make_message(), make_request(), latency_ms=None, batch=True)
    assert resp.batch and resp.usage.latency_ms is None
    assert resp.usage.cost_usd == pytest.approx(cost_usd("claude-sonnet-5-5", 1000, 200, 500, 100) * 0.5)


def test_real_sdk_client_gets_max_retries_zero() -> None:
    sdk = anthropic.Anthropic(api_key="test-key", max_retries=3)
    assert AnthropicClient(client=sdk)._client.max_retries == 0
