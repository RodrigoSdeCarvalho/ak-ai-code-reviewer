"""Append-only JSON-lines storage for analytics events."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from tracking.events import Event


class EventStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def append(self, event: Event) -> None:
        self.extend([event])

    def extend(self, events: Iterable[Event]) -> int:
        lines = [json.dumps(event.to_record(), sort_keys=True) + "\n" for event in events]
        with self._path.open("a", encoding="utf-8") as handle:
            handle.writelines(lines)
        return len(lines)

    def records(self, since: datetime | None = None, until: datetime | None = None) -> Iterator[dict[str, Any]]:
        """Yield stored records in write order, optionally limited to `since <= at < until`."""
        if not self._path.exists():
            return
        with self._path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                record = json.loads(line)
                at = datetime.fromisoformat(record["at"])
                if since is not None and at < since:
                    continue
                if until is not None and at >= until:
                    continue
                yield record

    def events(self, since: datetime | None = None, until: datetime | None = None) -> Iterator[Event]:
        return (Event.from_record(record) for record in self.records(since, until))

    def for_user(self, user_id: str) -> Iterator[dict[str, Any]]:
        """Records for one user, in write order."""
        return (record for record in self.records() if record.get("user_id") == user_id)
