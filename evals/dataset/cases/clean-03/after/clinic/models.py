"""Bookings and opening hours for a practitioner's calendar."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass(frozen=True)
class Booking:
    booking_id: str
    patient_id: str
    start: datetime
    end: datetime
    cancelled: bool = False

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"booking {self.booking_id} ends before it starts")


@dataclass(frozen=True)
class OpeningHours:
    """Opening and closing time per weekday (0 = Monday); days not listed are closed."""

    weekly: Mapping[int, tuple[time, time]]
    closed_dates: frozenset[date] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        for weekday, (opens, closes) in self.weekly.items():
            if not 0 <= weekday <= 6:
                raise ValueError(f"weekday must be 0-6, got {weekday}")
            if closes <= opens:
                raise ValueError(f"weekday {weekday} closes before it opens")

    def window_for(self, day: date) -> tuple[datetime, datetime] | None:
        """Opening interval on `day`, or None when the practice is closed."""
        if day in self.closed_dates:
            return None
        hours = self.weekly.get(day.weekday())
        if hours is None:
            return None
        opens, closes = hours
        return datetime.combine(day, opens), datetime.combine(day, closes)
