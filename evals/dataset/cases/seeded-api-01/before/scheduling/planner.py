"""Find meeting times that suit every attendee."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta

from scheduling.intervals import Interval, free_slots, merge_busy

Calendar = Sequence[Interval]


class NoCommonSlot(Exception):
    """Raised when the attendees share no free time of the requested length."""


def common_free_time(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
) -> list[Interval]:
    """Free intervals inside `window`, at least `length` long, shared by every attendee."""
    busy = [block for name in attendees for block in calendars[name]]
    return free_slots(merge_busy(busy), window, length)


def first_slot(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
) -> Interval:
    """Return the earliest slot of `length` that every attendee can make."""
    for free in common_free_time(calendars, attendees, window, length):
        return Interval(free.start, free.start + length)
    raise NoCommonSlot(f"no {length} slot for {', '.join(attendees)} between {window.start} and {window.end}")
