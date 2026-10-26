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
