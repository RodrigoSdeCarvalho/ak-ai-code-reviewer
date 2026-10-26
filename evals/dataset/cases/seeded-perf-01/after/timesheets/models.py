"""Records stored by the timesheet service."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


class UnknownRecord(LookupError):
    """Raised when an id does not match a stored record."""


@dataclass(frozen=True)
class Employee:
    id: int
    name: str
    weekly_capacity: Decimal


@dataclass(frozen=True)
class Project:
    id: int
    code: str
    name: str
    hourly_rate: Decimal
    billable: bool = True


@dataclass(frozen=True)
class Entry:
    id: int
    employee_id: int
    project_id: int
    day: date
    hours: Decimal


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("period end is before its start")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def weeks(self) -> Decimal:
        return Decimal(self.days) / Decimal(7)

    def __iter__(self) -> Iterator[date]:
        for offset in range(self.days):
            yield self.start + timedelta(days=offset)
