"""Time intervals and free-time computation for calendars."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"interval ends before it starts: {self.start} > {self.end}")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end


def merge_busy(
    intervals: Iterable[Interval],
    min_gap: timedelta = timedelta(0),
    padding: timedelta = timedelta(0),
) -> list[Interval]:
    """Merge busy intervals into a sorted list of disjoint intervals.

    Each interval is first widened by `padding` on both sides. Consecutive intervals separated by
    less than `min_gap` are then joined, since a free stretch that short cannot be used.
    """
    widened = sorted(Interval(i.start - padding, i.end + padding) for i in intervals)
    merged: list[Interval] = []
    for current in widened:
        if merged:
            gap = current.start - merged[-1].end
            if gap <= timedelta(0) or gap < min_gap:
                merged[-1] = Interval(merged[-1].start, max(merged[-1].end, current.end))
                continue
        merged.append(current)
    return merged


def free_slots(busy: list[Interval], window: Interval, length: timedelta) -> list[Interval]:
    """Return the free intervals inside `window` that are at least `length` long.

    `busy` must be sorted and disjoint, as returned by `merge_busy`.
    """
    free: list[Interval] = []
    cursor = window.start
    for block in busy:
        if block.end <= cursor:
            continue
        if block.start >= window.end:
            break
        if block.start - cursor >= length:
            free.append(Interval(cursor, block.start))
        cursor = max(cursor, block.end)
    if window.end - cursor >= length:
        free.append(Interval(cursor, window.end))
    return free
