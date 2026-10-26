"""Anthropic Messages API client: structured output, usage and cost, latency, retries, served-model check.

`build_params` and `message_to_response` are shared with the Message Batches client so a sync call and a
batch row produce identical requests and identical `LLMResponse` mapping.
"""

from __future__ import annotations

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import anthropic
from anthropic.types import Message

from aireview.llm.base import LLMRequest, LLMResponse
from aireview.models import Usage
from aireview.settings import cost_usd


def build_params(request: LLMRequest) -> dict[str, Any]:
    """Messages API parameters for one request. No temperature/top_p (rejected) and no thinking (adaptive)."""
    output_config: dict[str, Any] = {
        "format": {"type": "json_schema", "schema": anthropic.transform_schema(request.output_schema)}
    }
    if request.effort:
        output_config["effort"] = request.effort
    return {
        "model": request.model,
        "max_tokens": request.max_tokens,
        "system": [{"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": request.user}],
        "output_config": output_config,
    }


def served_model_matches(served: str | None, requested: str) -> bool:
    """The served id must be the requested alias or a dated snapshot of it."""
    return bool(served) and (served == requested or served.startswith(requested))


def message_to_response(
    message: Message,
    request: LLMRequest,
    *,
    latency_ms: int | None,
    batch: bool = False,
    attempts: int = 1,
) -> LLMResponse:
    """Map an API message to an `LLMResponse`, classifying every way it can fail to be usable."""
    u = message.usage
    cache_read = u.cache_read_input_tokens or 0
    cache_write = u.cache_creation_input_tokens or 0
    usage = Usage(
        input_tokens=u.input_tokens,
        output_tokens=u.output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
        cost_usd=cost_usd(request.model, u.input_tokens, u.output_tokens, cache_read, cache_write, batch=batch),
        latency_ms=latency_ms,
    )
    text = next((block.text for block in message.content if block.type == "text"), None)
    response = LLMResponse(
        raw_text=text,
        stop_reason=message.stop_reason,
        served_model=message.model,
        usage=usage,
        request_id=getattr(message, "_request_id", None),
        batch=batch,
        attempts=attempts,
    )
    if not served_model_matches(message.model, request.model):
        return _failed(response, f"served model {message.model!r} is not {request.model!r}", "model_mismatch")
    if message.stop_reason == "refusal":
        return _failed(response, "model refused (stop_reason=refusal)", "refused")
    if message.stop_reason == "max_tokens":
        return _failed(response, f"output truncated at max_tokens={request.max_tokens}", "truncated")
    if text is None:
        return _failed(response, "no text block in the response", "schema_error")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return _failed(response, f"output is not valid JSON: {exc}", "schema_error")
    if not isinstance(parsed, dict):
        return _failed(response, f"output is JSON {type(parsed).__name__}, not an object", "schema_error")
    return response.model_copy(update={"parsed": parsed})


def _failed(response: LLMResponse, error: str, error_class: str) -> LLMResponse:
    return response.model_copy(update={"error": error, "error_class": error_class})


def is_retryable(exc: anthropic.APIError) -> bool:
    if isinstance(exc, anthropic.APIConnectionError):  # includes APITimeoutError
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    return False


def _retry_after_s(exc: anthropic.APIError) -> float | None:
    if not isinstance(exc, anthropic.APIStatusError):
        return None
    try:
        return float(exc.response.headers.get("retry-after", ""))
    except ValueError:
        return None


class AnthropicClient:
    """Synchronous structured-output calls. Retries are ours (SDK `max_retries=0`) so they are counted."""

    def __init__(
        self,
        client: anthropic.Anthropic | None = None,
        max_attempts: int = 5,
        timeout_s: float = 300,
        concurrency: int = 4,
        backoff_base_s: float = 2.0,
        backoff_max_s: float = 60.0,
    ) -> None:
        if client is None:
            client = anthropic.Anthropic(max_retries=0)
        elif isinstance(client, anthropic.Anthropic):
            client = client.with_options(max_retries=0)
        self._client = client
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.concurrency = concurrency
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s

    def complete(self, request: LLMRequest) -> LLMResponse:
        """One call with retries on 429/5xx/connection errors, inside a hard `timeout_s` wall-clock ceiling."""
        cost_usd(request.model, 0, 0)  # an unpriced model fails before any spend
        params = build_params(request)
        deadline = time.monotonic() + self.timeout_s
        last_error = "no attempt made"
        for attempt in range(1, self.max_attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return self._timeout(attempt - 1, last_error)
            started = time.monotonic()
            try:
                message = self._client.messages.create(**params, timeout=remaining)
            except anthropic.APIError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if isinstance(exc, anthropic.APITimeoutError) and time.monotonic() >= deadline:
                    return self._timeout(attempt, last_error)
                if not is_retryable(exc):
                    return LLMResponse(
                        error=last_error,
                        error_class="api_error",
                        request_id=getattr(exc, "request_id", None),
                        attempts=attempt,
                    )
                if attempt < self.max_attempts:
                    delay = self._backoff(attempt, exc)
                    if time.monotonic() + delay >= deadline:
                        return self._timeout(attempt, last_error)
                    time.sleep(delay)
                continue
            latency_ms = int((time.monotonic() - started) * 1000)
            return message_to_response(message, request, latency_ms=latency_ms, attempts=attempt)
        return LLMResponse(
            error=f"gave up after {self.max_attempts} attempts; last: {last_error}",
            error_class="api_error",
            attempts=self.max_attempts,
        )

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        """Concurrent `complete` calls; results keep the request order."""
        if not requests:
            return []
        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            return list(pool.map(self.complete, requests))

    def _backoff(self, attempt: int, exc: anthropic.APIError) -> float:
        delay = min(self.backoff_max_s, self.backoff_base_s * 2 ** (attempt - 1)) * random.uniform(0.5, 1.0)
        retry_after = _retry_after_s(exc)
        if retry_after is not None:
            delay = max(delay, min(retry_after, self.backoff_max_s))
        return delay

    def _timeout(self, attempts: int, last_error: str) -> LLMResponse:
        return LLMResponse(
            error=f"exceeded {self.timeout_s}s wall-clock ceiling; last: {last_error}",
            error_class="timeout",
            attempts=attempts,
        )
