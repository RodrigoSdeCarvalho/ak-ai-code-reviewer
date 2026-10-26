"""Grouping of readings into continuous recording sessions."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import groupby
from operator import attrgetter

from telemetry.readings import Reading

DEFAULT_MAX_GAP = timedelta(minutes=15)


@dataclass(frozen=True)
class Session:
    """A run of readings from one device with no gap between consecutive samples longer than the maximum."""

    device_id: str
    started_at: datetime
    ended_at: datetime
    samples: int
    min_celsius: float
    max_celsius: float

    @property
    def duration(self) -> timedelta:
        return self.ended_at - self.started_at


def _split(points: list[Reading], max_gap: timedelta) -> Iterator[list[Reading]]:
    start = 0
    for i in range(1, len(points)):
        if points[i].taken_at - points[i - 1].taken_at > max_gap:
            yield points[start:i]
            start = i
    yield points[start:]


def _summarize(points: list[Reading]) -> Session:
    values = [point.celsius for point in points]
    return Session(
        device_id=points[0].device_id,
        started_at=points[0].taken_at,
        ended_at=points[-1].taken_at,
        samples=len(points),
        min_celsius=min(values),
        max_celsius=max(values),
    )


def sessionize(readings: Iterable[Reading], max_gap: timedelta = DEFAULT_MAX_GAP) -> Iterator[Session]:
    """Yield sessions ordered by device, then start time. Readings may arrive in any order.

    A gap of exactly `max_gap` keeps the two samples in the same session.
    """
    if max_gap <= timedelta(0):
        raise ValueError("max_gap must be positive")
    ordered = sorted(readings, key=attrgetter("device_id", "taken_at"))
    for _, group in groupby(ordered, key=attrgetter("device_id")):
        for points in _split(list(group), max_gap):
            yield _summarize(points)
