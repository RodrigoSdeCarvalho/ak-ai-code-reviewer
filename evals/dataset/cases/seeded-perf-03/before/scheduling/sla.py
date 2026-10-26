"""Support-ticket response targets expressed in business days."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from scheduling.calendar import BusinessCalendar

CUTOFF_HOUR = 17


class Priority(Enum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


TARGET_DAYS = {
    Priority.URGENT: 1,
    Priority.HIGH: 2,
    Priority.NORMAL: 5,
    Priority.LOW: 10,
}


@dataclass(frozen=True)
class Ticket:
    id: str
    opened_at: datetime
    priority: Priority


class SlaPolicy:
    def __init__(self, calendar: BusinessCalendar, cutoff_hour: int = CUTOFF_HOUR) -> None:
        self._calendar = calendar
        self._cutoff_hour = cutoff_hour

    def start_day(self, opened_at: datetime) -> date:
        """The ticket clock starts on the opening day, or the next business day if opened late."""
        day = opened_at.date()
        if self._calendar.is_business_day(day) and opened_at.hour < self._cutoff_hour:
            return day
        return self._calendar.roll_forward(day + timedelta(days=1))

    def due_date(self, ticket: Ticket) -> date:
        start = self.start_day(ticket.opened_at)
        return self._calendar.add_business_days(start, TARGET_DAYS[ticket.priority])

    def is_breached(self, ticket: Ticket, today: date) -> bool:
        return today > self.due_date(ticket)

    def overdue(self, tickets: Iterable[Ticket], today: date) -> list[tuple[Ticket, date]]:
        late = [(ticket, self.due_date(ticket)) for ticket in tickets]
        late = [(ticket, due) for ticket, due in late if today > due]
        return sorted(late, key=lambda pair: (pair[1], pair[0].id))
