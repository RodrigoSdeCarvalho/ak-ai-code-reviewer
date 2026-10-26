"""Product analytics events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EVENT_NAMES = frozenset({"signup", "login", "page_view", "purchase", "invite_sent"})


@dataclass(frozen=True)
class Event:
    name: str
    at: datetime
    user_id: str | None = None
    props: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name not in EVENT_NAMES:
            raise ValueError(f"unknown event name {self.name!r}")
        if self.at.tzinfo is None:
            raise ValueError("event time must be timezone-aware")

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "at": self.at.astimezone(timezone.utc).isoformat(),
            "user_id": self.user_id,
            "props": dict(self.props),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Event:
        return cls(
            name=record["name"],
            at=datetime.fromisoformat(record["at"]),
            user_id=record.get("user_id"),
            props=dict(record.get("props", {})),
        )
