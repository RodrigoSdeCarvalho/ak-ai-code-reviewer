"""Request limiters keyed by client id."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

Clock = Callable[[], float]


@dataclass(frozen=True)
class Decision:
    allowed: bool
    remaining: int
    retry_after: float


class Limiter(Protocol):
    def check(self, client_id: str, cost: int = 1) -> Decision: ...


class FixedWindowLimiter:
    """At most `limit` units of cost per client in each `window` seconds."""

    def __init__(self, limit: int, window: float, clock: Clock) -> None:
        if limit <= 0 or window <= 0:
            raise ValueError("limit and window must be positive")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._windows: dict[str, tuple[float, int]] = {}

    def check(self, client_id: str, cost: int = 1) -> Decision:
        now = self._clock()
        start, used = self._windows.get(client_id, (now, 0))
        if now - start >= self._window:
            start, used = now, 0
        if used + cost > self._limit:
            return Decision(False, self._limit - used, start + self._window - now)
        used += cost
        self._windows[client_id] = (start, used)
        return Decision(True, self._limit - used, 0.0)


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    """Up to `capacity` tokens per client, refilled continuously at `refill_rate` tokens per second."""

    def __init__(self, capacity: int, refill_rate: float, clock: Clock) -> None:
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")
        self._capacity = capacity
        self._rate = refill_rate
        self._clock = clock
        self._buckets: dict[str, _Bucket] = {}

    def check(self, client_id: str, cost: int = 1) -> Decision:
        now = self._clock()
        bucket = self._buckets.get(client_id)
        if bucket is None:
            bucket = self._buckets[client_id] = _Bucket(float(self._capacity), now)
        elapsed = max(0.0, now - bucket.updated_at)
        bucket.tokens = min(float(self._capacity), bucket.tokens + elapsed * self._rate)
        bucket.updated_at = now
        if bucket.tokens < cost:
            return Decision(False, int(bucket.tokens), (cost - bucket.tokens) / self._rate)
        bucket.tokens -= cost
        return Decision(True, int(bucket.tokens), 0.0)

    def reset(self, client_id: str) -> None:
        self._buckets.pop(client_id, None)
