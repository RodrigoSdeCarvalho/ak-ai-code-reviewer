"""Support-ticket response targets expressed in business days of the customer's region."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum

from scheduling.calendar import CalendarSet


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
    region: str


@dataclass(frozen=True)
class OverdueTicket:
    ticket: Ticket
    due: date
    days_late: int


class SlaPolicy:
    def __init__(self, calendars: CalendarSet) -> None:
        self._calendars = calendars

    def start_day(self, ticket: Ticket) -> date:
        """The ticket clock starts on the opening day, or the next business day if opened late."""
        calendar = self._calendars.for_region(ticket.region)
        day = ticket.opened_at.date()
        if calendar.is_business_day(day) and ticket.opened_at.hour < calendar.region.cutoff_hour:
            return day
        return calendar.roll_forward(day + timedelta(days=1))

    def due_date(self, ticket: Ticket) -> date:
        calendar = self._calendars.for_region(ticket.region)
        return calendar.add_business_days(self.start_day(ticket), TARGET_DAYS[ticket.priority])

    def is_breached(self, ticket: Ticket, today: date) -> bool:
        return today > self.due_date(ticket)

    def overdue(self, tickets: Iterable[Ticket], today: date) -> list[OverdueTicket]:
        late: list[OverdueTicket] = []
        for ticket in tickets:
            due = self.due_date(ticket)
            if today > due:
                late.append(OverdueTicket(ticket, due, (today - due).days))
        return sorted(late, key=lambda item: (item.due, item.ticket.id))

    def overdue_by_region(
        self, tickets: Iterable[Ticket], today: date
    ) -> dict[str, list[OverdueTicket]]:
        grouped: dict[str, list[OverdueTicket]] = defaultdict(list)
        for item in self.overdue(tickets, today):
            grouped[item.ticket.region].append(item)
        return {code: grouped.get(code, []) for code in self._calendars.codes}
