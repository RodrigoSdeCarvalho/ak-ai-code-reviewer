from __future__ import annotations

from itertools import count

from boxoffice.models import Event, EventStatus, Ticket, TicketStatus


class NotFound(LookupError):
    pass


class SoldOut(Exception):
    pass


class EventClosed(Exception):
    pass


class TicketStore:
    def __init__(self) -> None:
        self._events: dict[int, Event] = {}
        self._tickets: dict[int, Ticket] = {}
        self._ids = count(1)

    def add_event(self, event: Event) -> Event:
        self._events[event.id] = event
        return event

    def event(self, event_id: int) -> Event:
        try:
            return self._events[event_id]
        except KeyError:
            raise NotFound(f"event {event_id}") from None

    def ticket(self, ticket_id: int) -> Ticket:
        try:
            return self._tickets[ticket_id]
        except KeyError:
            raise NotFound(f"ticket {ticket_id}") from None

    def valid_tickets(self, event_id: int) -> list[Ticket]:
        return [t for t in self._tickets.values() if t.event_id == event_id and t.status is TicketStatus.VALID]

    def remaining(self, event_id: int) -> int:
        return self.event(event_id).capacity - len(self.valid_tickets(event_id))

    def sell(self, event_id: int, holder_id: int, quantity: int) -> list[Ticket]:
        event = self.event(event_id)
        if event.status is not EventStatus.ON_SALE:
            raise EventClosed(event.name)
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        if quantity > self.remaining(event_id):
            raise SoldOut(event.name)
        issued = []
        for _ in range(quantity):
            ticket = Ticket(next(self._ids), event_id, holder_id, event.price_cents)
            self._tickets[ticket.id] = ticket
            issued.append(ticket)
        return issued

    def refund(self, ticket_id: int) -> Ticket:
        ticket = self.ticket(ticket_id)
        ticket.status = TicketStatus.REFUNDED
        return ticket

    def cancel_event(self, event_id: int) -> int:
        event = self.event(event_id)
        refunded = 0
        for ticket in self.valid_tickets(event_id):
            ticket.status = TicketStatus.REFUNDED
            refunded += 1
        event.status = EventStatus.CANCELLED
        return refunded
