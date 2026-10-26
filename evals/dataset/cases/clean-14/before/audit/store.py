"""Append-only audit trail of administrative actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AuditEvent:
    id: int
    actor: str
    action: str
    target: str
    at: datetime


class AuditStore:
    """Events get consecutive ids starting at 1, in the order they are appended. Nothing is ever deleted."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def __len__(self) -> int:
        return len(self._events)

    def append(self, actor: str, action: str, target: str, at: datetime) -> AuditEvent:
        event = AuditEvent(len(self._events) + 1, actor, action, target, at)
        self._events.append(event)
        return event

    def get(self, event_id: int) -> AuditEvent | None:
        if 1 <= event_id <= len(self._events):
            return self._events[event_id - 1]
        return None

    def query(self, *, actor: str | None = None, action: str | None = None) -> list[AuditEvent]:
        """Matching events, newest first."""
        return [
            event
            for event in reversed(self._events)
            if (actor is None or event.actor == actor) and (action is None or event.action == action)
        ]
