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

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        before_id: int | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        """Matching events, newest first, with ids strictly below `before_id`; at most `limit` of them."""
        end = len(self._events) if before_id is None else max(0, min(before_id - 1, len(self._events)))
        matches: list[AuditEvent] = []
        for index in range(end - 1, -1, -1):
            if limit is not None and len(matches) >= limit:
                break
            event = self._events[index]
            if (actor is None or event.actor == actor) and (action is None or event.action == action):
                matches.append(event)
        return matches
