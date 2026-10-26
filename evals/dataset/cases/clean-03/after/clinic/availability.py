"""Availability checks for the booking flow."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from clinic.models import Booking, OpeningHours


class SlotUnavailable(Exception):
    """The requested time cannot be booked."""


@dataclass(frozen=True, order=True)
class Interval:
    start: datetime
    end: datetime


def overlaps(booking: Booking, start: datetime, end: datetime) -> bool:
    """True when the booking shares any time with [start, end); touching ends do not overlap."""
    return booking.start < end and start < booking.end


def conflicts(bookings: Iterable[Booking], start: datetime, end: datetime) -> list[Booking]:
    """Active bookings that overlap [start, end), ordered by start time."""
    hits = [b for b in bookings if not b.cancelled and overlaps(b, start, end)]
    return sorted(hits, key=lambda b: b.start)


def check_bookable(bookings: Iterable[Booking], hours: OpeningHours, start: datetime, end: datetime) -> None:
    """Raise SlotUnavailable unless [start, end) is inside opening hours and free."""
    if end <= start:
        raise SlotUnavailable("appointment must end after it starts")
    if start.date() != end.date():
        raise SlotUnavailable("appointments cannot span midnight")
    window = hours.window_for(start.date())
    if window is None:
        raise SlotUnavailable(f"closed on {start.date().isoformat()}")
    opens, closes = window
    if start < opens or end > closes:
        raise SlotUnavailable("outside opening hours")
    clashing = conflicts(bookings, start, end)
    if clashing:
        raise SlotUnavailable(f"overlaps booking {clashing[0].booking_id}")


def busy_intervals(bookings: Iterable[Booking]) -> list[Interval]:
    """Active bookings as sorted intervals, with overlapping or touching bookings merged."""
    merged: list[Interval] = []
    for current in sorted(Interval(b.start, b.end) for b in bookings if not b.cancelled):
        if merged and current.start <= merged[-1].end:
            merged[-1] = Interval(merged[-1].start, max(merged[-1].end, current.end))
        else:
            merged.append(current)
    return merged


def free_gaps(busy: list[Interval], window: Interval) -> list[Interval]:
    """Parts of `window` not covered by `busy`, which must come from busy_intervals."""
    inside = [
        Interval(max(b.start, window.start), min(b.end, window.end))
        for b in busy
        if b.start < window.end and window.start < b.end
    ]
    if not inside:
        return [window]
    gaps: list[Interval] = []
    if window.start < inside[0].start:
        gaps.append(Interval(window.start, inside[0].start))
    for i in range(len(inside) - 1):
        gaps.append(Interval(inside[i].end, inside[i + 1].start))
    if inside[-1].end < window.end:
        gaps.append(Interval(inside[-1].end, window.end))
    return gaps


def _slot_starts(gap: Interval, length: timedelta) -> Iterator[datetime]:
    """Back-to-back appointment start times that fit entirely inside `gap`."""
    start = gap.start
    while start + length <= gap.end:
        yield start
        start += length


def open_slots(
    bookings: Iterable[Booking],
    hours: OpeningHours,
    first_day: date,
    last_day: date,
    length: timedelta = timedelta(minutes=30),
) -> dict[date, list[datetime]]:
    """Free appointment start times for every day from `first_day` through `last_day`."""
    if last_day < first_day:
        raise ValueError("last_day is before first_day")
    if length <= timedelta(0):
        raise ValueError("appointment length must be positive")
    busy = busy_intervals(bookings)
    slots: dict[date, list[datetime]] = {}
    for offset in range((last_day - first_day).days + 1):
        day = first_day + timedelta(days=offset)
        window = hours.window_for(day)
        if window is None:
            slots[day] = []
            continue
        gaps = free_gaps(busy, Interval(*window))
        slots[day] = [start for gap in gaps for start in _slot_starts(gap, length)]
    return slots
