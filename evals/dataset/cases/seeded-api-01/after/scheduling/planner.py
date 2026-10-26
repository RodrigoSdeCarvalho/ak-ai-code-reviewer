"""Find meeting times that suit every attendee."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from scheduling.intervals import Interval, free_slots, merge_busy

Calendar = Sequence[Interval]


class NoCommonSlot(Exception):
    """Raised when the attendees share no free time of the requested length."""


@dataclass(frozen=True)
class PlannerSettings:
    """How suggested meetings are placed around existing commitments.

    `buffer` is kept free before and after every busy block, free stretches shorter than `min_gap`
    are not offered, and start times are rounded up to a multiple of `step` past the hour.
    """

    buffer: timedelta = timedelta(0)
    min_gap: timedelta = timedelta(0)
    step: timedelta = timedelta(minutes=1)

    def __post_init__(self) -> None:
        if self.step <= timedelta(0):
            raise ValueError("step must be positive")


DEFAULT_SETTINGS = PlannerSettings()


def _round_up(moment: datetime, step: timedelta) -> datetime:
    hour = moment.replace(minute=0, second=0, microsecond=0)
    remainder = (moment - hour) % step
    return moment + (step - remainder) if remainder else moment


def common_free_time(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
    settings: PlannerSettings = DEFAULT_SETTINGS,
) -> list[Interval]:
    """Free intervals inside `window`, at least `length` long, shared by every attendee."""
    busy = [block for name in attendees for block in calendars[name]]
    merged = merge_busy(busy, settings.buffer, settings.min_gap)
    return free_slots(merged, window, length)


def candidate_slots(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
    settings: PlannerSettings = DEFAULT_SETTINGS,
) -> Iterator[Interval]:
    """Yield every slot of `length` that all attendees can make, in time order, `step` apart."""
    for free in common_free_time(calendars, attendees, window, length, settings):
        start = _round_up(free.start, settings.step)
        while start + length <= free.end:
            yield Interval(start, start + length)
            start += settings.step


def suggest(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
    count: int = 3,
    settings: PlannerSettings = DEFAULT_SETTINGS,
) -> list[Interval]:
    """Return up to `count` non-overlapping slots, earliest first."""
    if count < 1:
        raise ValueError("count must be at least 1")
    picks: list[Interval] = []
    for slot in candidate_slots(calendars, attendees, window, length, settings):
        if picks and slot.overlaps(picks[-1]):
            continue
        picks.append(slot)
        if len(picks) == count:
            break
    return picks


def first_slot(
    calendars: Mapping[str, Calendar],
    attendees: Sequence[str],
    window: Interval,
    length: timedelta,
    settings: PlannerSettings = DEFAULT_SETTINGS,
) -> Interval:
    """Return the earliest slot of `length` that every attendee can make."""
    options = suggest(calendars, attendees, window, length, count=1, settings=settings)
    if not options:
        raise NoCommonSlot(f"no {length} slot for {', '.join(attendees)} between {window.start} and {window.end}")
    return options[0]
