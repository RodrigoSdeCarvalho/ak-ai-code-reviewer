"""Product analytics events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EVENT_NAMES = frozenset({"signup", "login", "logout", "page_view", "purchase", "invite_sent"})


@dataclass(frozen=True)
class Event:
    """One tracked action. `account_id` is None for anonymous visitors."""

    name: str
    at: datetime
    account_id: str | None = None
    props: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None

    def __post_init__(self) -> None:
        if self.name not in EVENT_NAMES:
            raise ValueError(f"unknown event name {self.name!r}")
        if self.at.tzinfo is None:
            raise ValueError("event time must be timezone-aware")

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "at": self.at.astimezone(timezone.utc).isoformat(),
            "account_id": self.account_id,
            "session_id": self.session_id,
            "props": dict(self.props),
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Event:
        record = upgrade_record(record)
        return cls(
            name=record["name"],
            at=datetime.fromisoformat(record["at"]),
            account_id=record.get("account_id"),
            session_id=record.get("session_id"),
            props=dict(record.get("props", {})),
        )


def upgrade_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return `record` in the current schema.

    Records written before accounts replaced users carry `user_id` and no `session_id`.
    """
    if "user_id" not in record:
        return record
    upgraded = {key: value for key, value in record.items() if key != "user_id"}
    upgraded.setdefault("account_id", record["user_id"])
    upgraded.setdefault("session_id", None)
    return upgraded
