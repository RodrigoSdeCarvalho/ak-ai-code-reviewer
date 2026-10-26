"""Business-day arithmetic over regional weekends and public holidays."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from scheduling.holidays import HolidaySource

DEFAULT_WEEKEND = frozenset({5, 6})
DEFAULT_CUTOFF_HOUR = 17


@dataclass(frozen=True)
class Region:
    code: str
    weekend: frozenset[int] = DEFAULT_WEEKEND
    cutoff_hour: int = DEFAULT_CUTOFF_HOUR

    def __post_init__(self) -> None:
        if len(self.weekend) >= 7:
            raise ValueError(f"{self.code}: a week needs at least one working day")
        if not 0 <= self.cutoff_hour <= 24:
            raise ValueError(f"{self.code}: cutoff hour must be between 0 and 24")


class BusinessCalendar:
    def __init__(self, source: HolidaySource, region: Region) -> None:
        self._source = source
        self._region = region

    @property
    def region(self) -> Region:
        return self._region

    def holidays(self, year: int) -> frozenset[date]:
        return frozenset(self._source.holidays(self._region.code, year))

    def is_business_day(self, day: date) -> bool:
        return day.weekday() not in self._region.weekend and day not in self.holidays(day.year)

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


class CalendarSet:
    """One business calendar per configured region, created on first use."""

    def __init__(self, source: HolidaySource, regions: Iterable[Region]) -> None:
        self._source = source
        self._regions = {region.code: region for region in regions}
        self._calendars: dict[str, BusinessCalendar] = {}

    @property
    def codes(self) -> list[str]:
        return sorted(self._regions)

    def for_region(self, code: str) -> BusinessCalendar:
        if code not in self._regions:
            raise KeyError(f"region {code!r} is not configured")
        if code not in self._calendars:
            self._calendars[code] = BusinessCalendar(self._source, self._regions[code])
        return self._calendars[code]
