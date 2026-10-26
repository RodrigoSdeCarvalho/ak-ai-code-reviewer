"""Availability checks for the booking flow."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from clinic.models import Booking, OpeningHours


class SlotUnavailable(Exception):
    """The requested time cannot be booked."""


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
