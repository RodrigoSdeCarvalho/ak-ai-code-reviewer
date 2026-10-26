from __future__ import annotations

from datetime import datetime
from itertools import count

from bookclub.models import JournalEntry, NotFound


class EntryStore:
    def __init__(self) -> None:
        self._entries: dict[int, JournalEntry] = {}
        self._ids = count(1)

    def create(self, owner_id: int, book_title: str, body: str, now: datetime) -> JournalEntry:
        entry = JournalEntry(next(self._ids), owner_id, book_title, body, now, now)
        self._entries[entry.id] = entry
        return entry

    def get(self, entry_id: int) -> JournalEntry:
        try:
            return self._entries[entry_id]
        except KeyError:
            raise NotFound(f"journal entry {entry_id} does not exist") from None

    def owned_by(self, user_id: int) -> list[JournalEntry]:
        return sorted(
            (e for e in self._entries.values() if e.owner_id == user_id),
            key=lambda e: e.updated_at,
            reverse=True,
        )

    def shared_with(self, user_id: int) -> list[JournalEntry]:
        return sorted(
            (e for e in self._entries.values() if user_id in e.readers),
            key=lambda e: e.updated_at,
            reverse=True,
        )
