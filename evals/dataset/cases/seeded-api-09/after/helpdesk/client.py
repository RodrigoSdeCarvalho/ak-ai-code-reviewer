"""Thin client for the helpdesk vendor's REST API."""

from __future__ import annotations

import time
from typing import Any, Protocol

DEFAULT_ATTEMPTS = 3


class TransportError(Exception):
    """The request may or may not have reached the server (timeout, reset connection)."""


class ApiError(Exception):
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        super().__init__(f"helpdesk API returned {status}: {payload.get('message', '')}")
        self.status = status
        self.payload = payload


class Transport(Protocol):
    def send(
        self, method: str, url: str, headers: dict[str, str], json: dict[str, Any] | None
    ) -> tuple[int, dict[str, Any]]: ...


class HelpdeskClient:
    def __init__(self, transport: Transport, base_url: str, token: str, backoff_seconds: float = 0.5) -> None:
        self._transport = transport
        self._backoff = backoff_seconds
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def request(
        self, method: str, path: str, *, max_attempts: int = DEFAULT_ATTEMPTS, **fields: Any
    ) -> dict[str, Any]:
        """Call the API and return the decoded response body.

        Keyword arguments other than `max_attempts` form the JSON body. Transport errors and 5xx
        answers are retried up to `max_attempts` times in total, with exponential backoff between
        attempts; 4xx answers raise ApiError at once.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        url = f"{self._base_url}/{path.lstrip('/')}"
        body = fields or None
        error: Exception | None = None
        for attempt in range(max_attempts):
            if attempt:
                time.sleep(min(self._backoff * 2 ** (attempt - 1), 8.0))
            try:
                status, payload = self._transport.send(method, url, self._headers, body)
            except TransportError as exc:
                error = exc
                continue
            if status >= 500:
                error = ApiError(status, payload)
                continue
            if status >= 400:
                raise ApiError(status, payload)
            return payload
        assert error is not None
        raise error
