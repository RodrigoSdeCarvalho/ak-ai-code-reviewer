"""Handlers for the admin audit API. The web layer passes in the query parameters and serialises the Response."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from audit.store import AuditEvent, AuditStore

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
_CURSOR = re.compile(r"v1:([1-9][0-9]*)")


@dataclass(frozen=True)
class Response:
    status: int
    body: dict[str, Any]


class BadRequest(ValueError):
    pass


def _serialize(event: AuditEvent) -> dict[str, Any]:
    return {
        "id": event.id,
        "actor": event.actor,
        "action": event.action,
        "target": event.target,
        "at": event.at.isoformat(),
    }


def encode_cursor(event_id: int) -> str:
    return base64.urlsafe_b64encode(f"v1:{event_id}".encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    except ValueError:
        raise BadRequest("malformed cursor") from None
    match = _CURSOR.fullmatch(raw)
    if match is None:
        raise BadRequest("malformed cursor")
    return int(match.group(1))


def _page_size(raw: str | None) -> int:
    if raw is None:
        return DEFAULT_PAGE_SIZE
    try:
        size = int(raw)
    except ValueError:
        raise BadRequest("limit must be an integer") from None
    if size < 1:
        raise BadRequest("limit must be at least 1")
    return min(size, MAX_PAGE_SIZE)


def list_events(store: AuditStore, params: Mapping[str, str]) -> Response:
    """GET /audit/events?actor=&action=&limit=&cursor= : one page of matching events, newest first.

    `next_cursor` is null on the last page; otherwise pass it back as `cursor` to get the next page.
    """
    try:
        limit = _page_size(params.get("limit"))
        before_id = decode_cursor(params["cursor"]) if "cursor" in params else None
    except BadRequest as exc:
        return Response(400, {"error": str(exc)})
    rows = store.query(actor=params.get("actor"), action=params.get("action"), before_id=before_id, limit=limit + 1)
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1].id) if len(rows) > limit else None
    return Response(200, {"events": [_serialize(event) for event in page], "next_cursor": next_cursor})


def get_event(store: AuditStore, event_id: str) -> Response:
    """GET /audit/events/{event_id}"""
    if not event_id.isdecimal():
        return Response(404, {"error": "not found"})
    event = store.get(int(event_id))
    if event is None:
        return Response(404, {"error": "not found"})
    return Response(200, _serialize(event))
