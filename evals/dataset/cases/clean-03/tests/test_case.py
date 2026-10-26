from datetime import date, datetime, time, timedelta

import pytest

from clinic.availability import Interval, busy_intervals, check_bookable, free_gaps, open_slots
from clinic.models import Booking, OpeningHours

MON = date(2026, 11, 2)
HOURS = OpeningHours(
    weekly={0: (time(9), time(12)), 1: (time(9), time(12)), 2: (time(14), time(16))},
    closed_dates=frozenset({date(2026, 11, 3)}),
)


def at(day, hh, mm=0):
    return datetime.combine(day, time(hh, mm))


def booking(bid, day, start, end, cancelled=False):
    return Booking(bid, "p-" + bid, at(day, *start), at(day, *end), cancelled)


def hhmm(slots):
    return [s.strftime("%H:%M") for s in slots]


def test_single_day_range_is_included():
    slots = open_slots([], HOURS, MON, MON, length=timedelta(hours=1))
    assert list(slots) == [MON]
    assert hhmm(slots[MON]) == ["09:00", "10:00", "11:00"]


def test_last_day_is_included_and_closed_days_are_empty():
    slots = open_slots([], HOURS, MON, MON + timedelta(days=3), length=timedelta(hours=1))
    assert list(slots) == [MON + timedelta(days=i) for i in range(4)]
    assert slots[MON + timedelta(days=1)] == []
    assert hhmm(slots[MON + timedelta(days=2)]) == ["14:00", "15:00"]
    assert slots[MON + timedelta(days=3)] == []


def test_gaps_between_every_pair_of_bookings_and_after_the_last():
    bookings = [
        booking("a", MON, (9, 30), (10, 0)),
        booking("b", MON, (10, 30), (11, 0)),
        booking("c", MON, (11, 15), (11, 30)),
        booking("x", MON, (9, 0), (12, 0), cancelled=True),
    ]
    slots = open_slots(bookings, HOURS, MON, MON, length=timedelta(minutes=15))
    assert hhmm(slots[MON]) == ["09:00", "09:15", "10:00", "10:15", "11:00", "11:30", "11:45"]


def test_touching_and_overlapping_bookings_merge():
    bookings = [
        booking("a", MON, (9, 0), (10, 0)),
        booking("b", MON, (10, 0), (10, 30)),
        booking("c", MON, (10, 15), (10, 45)),
    ]
    assert busy_intervals(bookings) == [Interval(at(MON, 9), at(MON, 10, 45))]
    window = Interval(at(MON, 9), at(MON, 12))
    assert free_gaps(busy_intervals(bookings), window) == [Interval(at(MON, 10, 45), at(MON, 12))]


def test_bookings_outside_the_window_are_ignored():
    bookings = [booking("early", MON, (7, 0), (9, 30)), booking("late", MON, (11, 30), (13, 0))]
    window = Interval(at(MON, 9), at(MON, 12))
    assert free_gaps(busy_intervals(bookings), window) == [Interval(at(MON, 9, 30), at(MON, 11, 30))]


def test_fully_booked_day_has_no_slots():
    slots = open_slots([booking("all", MON, (8, 0), (13, 0))], HOURS, MON, MON)
    assert slots[MON] == []


def test_every_listed_slot_is_bookable():
    bookings = [booking("a", MON, (9, 20), (9, 50)), booking("b", MON, (10, 40), (11, 10))]
    length = timedelta(minutes=20)
    for day, starts in open_slots(bookings, HOURS, MON, MON + timedelta(days=2), length).items():
        for start in starts:
            check_bookable(bookings, HOURS, start, start + length)


@pytest.mark.parametrize(("first", "last", "length"), [(MON, MON - timedelta(days=1), timedelta(minutes=30)), (MON, MON, timedelta(0))])
def test_invalid_arguments(first, last, length):
    with pytest.raises(ValueError):
        open_slots([], HOURS, first, last, length)
