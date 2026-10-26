from datetime import datetime, timedelta

import pytest
from scheduling.intervals import Interval
from scheduling.planner import NoCommonSlot, PlannerSettings, first_slot, suggest


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, 10, hour, minute)


CALENDARS = {
    "ana": [Interval(at(10), at(11))],
    "ben": [Interval(at(13), at(14))],
}
HALF_HOUR = timedelta(minutes=30)


def test_buffer_is_kept_after_a_meeting():
    settings = PlannerSettings(buffer=timedelta(minutes=15), step=timedelta(minutes=15))
    slot = first_slot(CALENDARS, ["ana", "ben"], Interval(at(10, 30), at(17)), HALF_HOUR, settings)
    assert slot == Interval(at(11, 15), at(11, 45))


def test_buffer_is_kept_before_a_meeting():
    settings = PlannerSettings(buffer=timedelta(minutes=15), step=timedelta(minutes=15))
    picks = suggest(CALENDARS, ["ana", "ben"], Interval(at(11, 30), at(14, 30)), HALF_HOUR, 5, settings)
    assert picks == [
        Interval(at(11, 30), at(12)),
        Interval(at(12), at(12, 30)),
    ]


def test_short_gaps_are_not_offered():
    calendars = {"ana": [Interval(at(9), at(10)), Interval(at(10, 30), at(12))]}
    settings = PlannerSettings(min_gap=timedelta(minutes=45))
    with pytest.raises(NoCommonSlot):
        first_slot(calendars, ["ana"], Interval(at(9), at(12)), HALF_HOUR, settings)


def test_default_settings_and_rounding():
    assert first_slot(CALENDARS, ["ana", "ben"], Interval(at(9), at(17)), HALF_HOUR) == Interval(at(9), at(9, 30))
    calendars = {"ana": [Interval(at(9), at(9, 7))]}
    assert first_slot(calendars, ["ana"], Interval(at(9), at(9, 37)), HALF_HOUR) == Interval(at(9, 7), at(9, 37))
    five = PlannerSettings(step=timedelta(minutes=5))
    assert first_slot(calendars, ["ana"], Interval(at(9), at(10)), HALF_HOUR, five) == Interval(at(9, 10), at(9, 40))
    picks = suggest(CALENDARS, ["ana", "ben"], Interval(at(9), at(11)), HALF_HOUR, count=3)
    assert picks == [Interval(at(9), at(9, 30)), Interval(at(9, 30), at(10))]
