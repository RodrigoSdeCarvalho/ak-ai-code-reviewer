"""Per-tenant API call counting for the monthly usage export."""

from __future__ import annotations

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
    def __init__(self) -> None:
        self._calls: Counter[str] = Counter()

    def record(self, tenant: str, calls: int = 1) -> None:
        if calls < 1:
            raise ValueError("calls must be positive")
        self._calls[tenant] += calls

    def count(self, tenant: str) -> int:
        return self._calls[tenant]

    def snapshot(self, now: datetime) -> UsageSnapshot:
        return UsageSnapshot(now, dict(self._calls))

    def drain(self, now: datetime) -> UsageSnapshot:
        """Return the counts so far and start a new period from zero."""
        snapshot = self.snapshot(now)
        self._calls.clear()
        return snapshot
