from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class User:
    id: int
    display_name: str


@dataclass
class JournalEntry:
    """A member's notes on a book. Only the owner may change it; readers may view it."""

    id: int
    owner_id: int
    book_title: str
    body: str
    created_at: datetime
    updated_at: datetime
    readers: set[int] = field(default_factory=set)

    def summary(self) -> dict[str, object]:
        return {
            "id": self.id,
            "book_title": self.book_title,
            "excerpt": self.body[:120],
            "updated_at": self.updated_at.isoformat(),
            "shared": bool(self.readers),
        }

    def detail(self) -> dict[str, object]:
        return {
            "id": self.id,
            "owner_id": self.owner_id,
            "book_title": self.book_title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reader_count": len(self.readers),
        }


class NotFound(Exception):
    pass
