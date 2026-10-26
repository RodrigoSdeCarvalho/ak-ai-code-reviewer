"""Click events read from JSON-lines exports."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    event_id: str
    user_id: str
    ip: str
    path: str
    country: str | None = None


def parse_line(line: str) -> Event | None:
    """Parse one exported line; None for blank or malformed lines."""
    line = line.strip()
    if not line:
        return None
    try:
        raw = json.loads(line)
        return Event(str(raw["id"]), str(raw["user"]), str(raw["ip"]), str(raw["path"]))
    except (ValueError, KeyError, TypeError):
        return None


def to_json(event: Event) -> str:
    return json.dumps(
        {
            "id": event.event_id,
            "user": event.user_id,
            "ip": event.ip,
            "path": event.path,
            "country": event.country,
        },
        separators=(",", ":"),
    )
