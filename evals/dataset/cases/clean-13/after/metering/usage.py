"""Per-tenant API call counting for the monthly usage export."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class UsageSnapshot:
    taken_at: datetime
    calls: Mapping[str, int]

    @property
    def total(self) -> int:
        return sum(self.calls.values())

    def to_csv_rows(self) -> list[str]:
        """One `tenant,calls` row per tenant, busiest first, ties by tenant id."""
        ordered = sorted(self.calls.items(), key=lambda item: (-item[1], item[0]))
        return [f"{tenant},{calls}" for tenant, calls in ordered]


class UsageMeter:
    """Shared by all request-handler threads of a worker process."""

    def __init__(self, initial: Mapping[str, int] = {}) -> None:
        self._calls: Counter[str] = Counter(initial)
        self._lock = threading.Lock()

    def record(self, tenant: str, calls: int = 1) -> None:
        if calls < 1:
            raise ValueError("calls must be positive")
        with self._lock:
            self._calls[tenant] += calls

    def count(self, tenant: str) -> int:
        with self._lock:
            return self._calls[tenant]

    def snapshot(self, now: datetime) -> UsageSnapshot:
        with self._lock:
            calls = dict(self._calls)
        return UsageSnapshot(now, calls)

    def drain(self, now: datetime) -> UsageSnapshot:
        """Return the counts so far and start a new period from zero."""
        with self._lock:
            calls, self._calls = self._calls, Counter()
        return UsageSnapshot(now, dict(calls))
