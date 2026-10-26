"""Aggregate reports over stored analytics events."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from tracking.store import EventStore

Record = dict[str, Any]


def _day(record: Record) -> date:
    return datetime.fromisoformat(record["at"]).date()


def daily_counts(records: Iterable[Record], name: str) -> dict[date, int]:
    """Number of `name` events per UTC day, in day order."""
    counts: dict[date, int] = defaultdict(int)
    for record in records:
        if record["name"] == name:
            counts[_day(record)] += 1
    return dict(sorted(counts.items()))


def top_users(records: Iterable[Record], n: int = 10, name: str | None = None) -> list[tuple[str, int]]:
    """The `n` users with the most events (of `name`, if given), most active first."""
    counts = Counter(
        record["user_id"]
        for record in records
        if record.get("user_id") is not None and (name is None or record["name"] == name)
    )
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]


def user_timeline(store: EventStore, user_id: str) -> list[tuple[datetime, str]]:
    """Every event of one user as (time, name), oldest first."""
    return sorted((datetime.fromisoformat(record["at"]), record["name"]) for record in store.for_user(user_id))
