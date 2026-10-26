"""Business-day arithmetic over weekends and public holidays."""

from __future__ import annotations

from datetime import date, timedelta

from scheduling.holidays import HolidaySource

DEFAULT_WEEKEND = frozenset({5, 6})


class BusinessCalendar:
    def __init__(self, source: HolidaySource, weekend: frozenset[int] = DEFAULT_WEEKEND) -> None:
        if len(weekend) >= 7:
            raise ValueError("a week needs at least one working day")
        self._source = source
        self._weekend = weekend
        self._holidays_by_year: dict[int, frozenset[date]] = {}

    def holidays(self, year: int) -> frozenset[date]:
        if year not in self._holidays_by_year:
            self._holidays_by_year[year] = frozenset(self._source.holidays(year))
        return self._holidays_by_year[year]

    def is_business_day(self, day: date) -> bool:
        return day.weekday() not in self._weekend and day not in self.holidays(day.year)

    def roll_forward(self, day: date) -> date:
        while not self.is_business_day(day):
            day += timedelta(days=1)
        return day

    def add_business_days(self, start: date, days: int) -> date:
        step = 1 if days >= 0 else -1
        remaining = abs(days)
        current = start
        while remaining:
            current += timedelta(days=step)
            if self.is_business_day(current):
                remaining -= 1
        return current

    def business_days_between(self, start: date, end: date) -> int:
        """Business days in (start, end]; negative when end is before start."""
        if end < start:
            return -self.business_days_between(end, start)
        count = 0
        current = start
        while current < end:
            current += timedelta(days=1)
            if self.is_business_day(current):
                count += 1
        return count
