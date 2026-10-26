"""Handlers for the admin audit API. The web layer passes in the query parameters and serialises the Response."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from audit.store import AuditEvent, AuditStore


@dataclass(frozen=True)
class Response:
    status: int
    body: dict[str, Any]


def _serialize(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "target": event.target,
        "at": event.at.isoformat(),
    }


def list_events(store: AuditStore, params: Mapping[str, str]) -> Response:
    """GET /audit/events?actor=&action= : matching events, newest first."""
    events = store.query(actor=params.get("actor"), action=params.get("action"))
    return Response(200, {"events": [_serialize(event) for event in events]})


def get_event(store: AuditStore, event_id: str) -> Response:
    """GET /audit/events/{event_id}"""
    if not event_id.isdecimal():
        return Response(404, {"error": "not found"})
    event = store.get(int(event_id))
    if event is None:
        return Response(404, {"error": "not found"})
    return Response(200, _serialize(event))
