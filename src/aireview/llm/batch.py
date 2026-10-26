"""Message Batches path for record mode: one batch per `complete_many`, 50% cost, latency not measured."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, cast

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from aireview.llm.anthropic_client import build_params, is_retryable, message_to_response
from aireview.llm.base import LLMRequest, LLMResponse, is_model_outcome
from aireview.llm.cassette import BudgetTracker, CassetteConflict, CassetteStore, conflict_message


class BatchClient:
    """Submits all pending requests as one Message Batch, waits for it, stores and returns the answers."""

    def __init__(
        self,
        store: CassetteStore,
        budget: BudgetTracker | None = None,
        poll_s: float = 30,
        max_wait_s: float = 7200,
        *,
        resume: bool = False,
        client: Any | None = None,
        cancel_wait_s: float = 900,
        api_attempts: int = 5,
    ) -> None:
        self.store = store
        self.budget = budget
        self.poll_s = poll_s
        self.max_wait_s = max_wait_s
        self.cancel_wait_s = cancel_wait_s
        self.api_attempts = api_attempts
        self.resume = resume
        self._client = client if client is not None else anthropic.Anthropic()

    def complete(self, request: LLMRequest) -> LLMResponse:
        return self.complete_many([request])[0]

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        """Responses in request order. Cassettes are reused only with `resume`; duplicates share one row."""
        out: list[LLMResponse | None] = [None] * len(requests)
        pending: dict[str, list[int]] = {}
        for i, request in enumerate(requests):
            cached = self.store.get(request) if self.resume else None
            if cached is not None:
                out[i] = cached
            else:
                pending.setdefault(request.key(), []).append(i)
        if not self.resume:
            existing = [requests[idx[0]] for idx in pending.values() if self.store.exists(requests[idx[0]])]
            if existing:
                raise CassetteConflict(conflict_message(len(existing)))
        if pending:
            by_key = {key: requests[idx[0]] for key, idx in pending.items()}
            for key, response in self._run_batch(by_key).items():
                for i in pending[key]:
                    out[i] = response
        return cast(list[LLMResponse], out)

    def _api[T](self, call: Callable[[], T]) -> T:
        """One batches-API call, retried on 429/5xx/connection errors (the batch may already be paid for)."""
        for attempt in range(1, self.api_attempts + 1):
            try:
                return call()
            except anthropic.APIError as exc:
                if attempt == self.api_attempts or not is_retryable(exc):
                    raise
                time.sleep(min(60.0, 2.0 * 2 ** (attempt - 1)))
        raise AssertionError("unreachable")

    def _run_batch(self, by_key: dict[str, LLMRequest]) -> dict[str, LLMResponse]:
        if self.budget is not None:
            self.budget.check()
        batch_requests = [
            Request(custom_id=key, params=MessageCreateParamsNonStreaming(**build_params(req)))
            for key, req in by_key.items()
        ]
        try:
            batch = self._client.messages.batches.create(requests=batch_requests)
        except anthropic.APIError as exc:
            return {key: _error(f"batch create failed: {type(exc).__name__}: {exc}", "api_error") for key in by_key}
        canceled = False
        try:
            if not self._wait(batch.id, self.max_wait_s):
                # Rows that finished before the cancel are billed: wait for the batch to end and read them.
                canceled = True
                self._api(lambda: self._client.messages.batches.cancel(batch.id))
                if not self._wait(batch.id, self.cancel_wait_s):
                    msg = f"batch {batch.id} not ended after {self.max_wait_s}s and did not end after cancel"
                    return {key: _error(msg, "timeout", batch.id) for key in by_key}
            rows = self._api(lambda: list(self._client.messages.batches.results(batch.id)))
        except anthropic.APIError as exc:
            msg = f"batch {batch.id}: {type(exc).__name__}: {exc}; record again with --resume"
            return {key: _error(msg, "api_error", batch.id) for key in by_key}

        results: dict[str, LLMResponse] = {}
        for row in rows:
            request = by_key.get(row.custom_id)
            if request is None:
                continue
            response = _row_to_response(row.result, request, batch.id, canceled=canceled)
            results[row.custom_id] = response
            if self.budget is not None:
                self.budget.add(response.usage.cost_usd)
            if is_model_outcome(response):
                self.store.put(request, response)
        for key in by_key.keys() - results.keys():
            results[key] = _error(f"batch {batch.id} returned no result for {key}", "api_error", batch.id)
        return results

    def _wait(self, batch_id: str, max_wait_s: float) -> bool:
        deadline = time.monotonic() + max_wait_s
        while True:
            status = self._api(lambda: self._client.messages.batches.retrieve(batch_id)).processing_status
            if status == "ended":
                return True
            if time.monotonic() + self.poll_s > deadline:
                return False
            time.sleep(self.poll_s)


def _row_to_response(result: Any, request: LLMRequest, batch_id: str, *, canceled: bool = False) -> LLMResponse:
    """Map one batch result (succeeded / errored / canceled / expired) to an `LLMResponse`."""
    if result.type == "succeeded":
        response = message_to_response(result.message, request, latency_ms=None, batch=True)
        return response.model_copy(update={"request_id": batch_id})
    if result.type == "errored":
        err = result.error.error
        return _error(f"batch row errored: {err.type}: {err.message}", "api_error", batch_id)
    if result.type == "expired":
        return _error("batch row expired before processing", "timeout", batch_id)
    if result.type == "canceled" and canceled:
        return _error(f"batch {batch_id} canceled after the wait limit before this row ran", "timeout", batch_id)
    return _error(f"batch row {result.type}", "api_error", batch_id)


def _error(message: str, error_class: str, batch_id: str | None = None) -> LLMResponse:
    return LLMResponse(error=message, error_class=error_class, request_id=batch_id, batch=True)
