"""Job definitions for the scheduler."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Job:
    """A callable run every `interval`, starting at `next_run`."""

    name: str
    interval: timedelta
    action: Callable[[], None]
    next_run: datetime
    enabled: bool = True
    consecutive_failures: int = 0
    last_success: datetime | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        if self.interval <= timedelta(0):
            raise ValueError(f"job {self.name!r}: interval must be positive")


def every(
    name: str, interval: timedelta, action: Callable[[], None], start: datetime
) -> Job:
    """Build a job that first runs at `start` and then every `interval`."""
    return Job(name=name, interval=interval, action=action, next_run=start)


def daily_at(name: str, action: Callable[[], None], first_day: datetime, hour: int) -> Job:
    """Build a job that runs once a day at `hour`:00, starting on `first_day`."""
    if not 0 <= hour < 24:
        raise ValueError("hour must be in 0..23")
    start = first_day.replace(hour=hour, minute=0, second=0, microsecond=0)
    return Job(name=name, interval=timedelta(days=1), action=action, next_run=start)
