from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Role(Enum):
    ATTENDEE = "attendee"
    STAFF = "staff"
    ADMIN = "admin"


class EventStatus(Enum):
    ON_SALE = "on_sale"
    CANCELLED = "cancelled"


class TicketStatus(Enum):
    VALID = "valid"
    REFUNDED = "refunded"


@dataclass(frozen=True)
class User:
    id: int
    name: str
    role: Role = Role.ATTENDEE


@dataclass
class Event:
    id: int
    name: str
    capacity: int
    price_cents: int
    status: EventStatus = EventStatus.ON_SALE


@dataclass
class Ticket:
    id: int
    event_id: int
    holder_id: int
    price_paid_cents: int
    status: TicketStatus = TicketStatus.VALID
    comp_issued_by: int | None = None
    comp_note: str = ""

    @property
    def is_comp(self) -> bool:
        return self.comp_issued_by is not None


@dataclass
class Request:
    user: User | None
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class Response:
    status: int
    body: dict[str, object] = field(default_factory=dict)
