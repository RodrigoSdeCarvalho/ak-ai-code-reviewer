"""Outbound webhook delivery to subscriber endpoints."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
Sleep = Callable[[float], None]


class Transport(Protocol):
    def post(self, url: str, body: bytes, headers: dict[str, str]) -> int:
        """Send the request and return the HTTP status code."""
        ...


class DeliveryError(Exception):
    """The endpoint could not be reached or did not answer with a 2xx status."""

    def __init__(self, endpoint: str, status: int | None) -> None:
        super().__init__(f"{endpoint}: " + ("unreachable" if status is None else f"HTTP {status}"))
        self.endpoint = endpoint
        self.status = status


@dataclass(frozen=True)
class Event:
    id: str
    type: str
    payload: dict[str, object]

    def body(self) -> bytes:
        return json.dumps({"id": self.id, "type": self.type, "data": self.payload}, sort_keys=True).encode()


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 8.0

    def delay(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * 2 ** (attempt - 1))


def post_once(transport: Transport, endpoint: str, event: Event) -> None:
    headers = {"Content-Type": "application/json", "Idempotency-Key": event.id}
    try:
        status = transport.post(endpoint, event.body(), headers)
    except (ConnectionError, TimeoutError) as exc:
        raise DeliveryError(endpoint, None) from exc
    if not 200 <= status < 300:
        raise DeliveryError(endpoint, status)


def deliver(
    transport: Transport, endpoint: str, event: Event, policy: RetryPolicy = RetryPolicy(), sleep: Sleep = time.sleep
) -> int:
    """Post the event to one endpoint. Returns the number of attempts made."""
    attempt = 1
    while True:
        try:
            post_once(transport, endpoint, event)
            return attempt
        except DeliveryError as error:
            if attempt >= policy.attempts or error.status not in RETRYABLE_STATUSES | {None}:
                raise
        sleep(policy.delay(attempt))
        attempt += 1


def broadcast(transport: Transport, endpoints: list[str], event: Event) -> dict[str, DeliveryError]:
    """Deliver to every endpoint; one failing subscriber does not stop the others. Returns the failures."""
    failures: dict[str, DeliveryError] = {}
    for endpoint in endpoints:
        try:
            deliver(transport, endpoint, event)
        except DeliveryError as exc:
            failures[endpoint] = exc
    return failures
