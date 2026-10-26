"""Aggregate reports over stored analytics events."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from tracking.store import EventStore

Record = dict[str, Any]


def _at(record: Record) -> datetime:
    return datetime.fromisoformat(record["at"])


def _day(record: Record) -> date:
    return _at(record).date()


def daily_counts(records: Iterable[Record], name: str) -> dict[date, int]:
    """Number of `name` events per UTC day, in day order."""
    counts: dict[date, int] = defaultdict(int)
    for record in records:
        if record["name"] == name:
            counts[_day(record)] += 1
    return dict(sorted(counts.items()))


def top_accounts(records: Iterable[Record], n: int = 10, name: str | None = None) -> list[tuple[str, int]]:
    """The `n` accounts with the most events (of `name`, if given), most active first."""
    counts = Counter(
        record["account_id"]
        for record in records
        if record.get("account_id") is not None and (name is None or record["name"] == name)
    )
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:n]


def daily_active_accounts(records: Iterable[Record]) -> dict[date, int]:
    """Distinct signed-in accounts with at least one event, per UTC day, in day order."""
    active: dict[date, set[str]] = defaultdict(set)
    for record in records:
        account = record.get("account_id")
        if account is not None:
            active[_day(record)].add(account)
    return {day: len(accounts) for day, accounts in sorted(active.items())}


def retention(records: Iterable[Record], cohort_day: date, horizon: int = 7) -> list[float]:
    """Share of the accounts that signed up on `cohort_day` that were active on each following day.

    Element 0 is the day after signup, up to `horizon` days. An empty cohort gives all zeros.
    """
    if horizon < 1:
        raise ValueError("horizon must be at least 1")
    cohort: set[str] = set()
    active_days: dict[str, set[date]] = defaultdict(set)
    for record in records:
        account = record.get("account_id")
        if account is None:
            continue
        day = _day(record)
        if record["name"] == "signup" and day == cohort_day:
            cohort.add(account)
        active_days[account].add(day)
    if not cohort:
        return [0.0] * horizon
    shares: list[float] = []
    for offset in range(1, horizon + 1):
        target = cohort_day + timedelta(days=offset)
        returning = sum(1 for account in cohort if target in active_days[account])
        shares.append(returning / len(cohort))
    return shares


@dataclass
class SessionStats:
    account_id: str | None
    started: datetime
    ended: datetime
    events: int

    @property
    def duration(self) -> timedelta:
        return self.ended - self.started


def session_stats(records: Iterable[Record]) -> dict[str, SessionStats]:
    """Per session id: the account that signed in (if any), first and last event time, event count."""
    sessions: dict[str, SessionStats] = {}
    for record in records:
        session_id = record.get("session_id")
        if session_id is None:
            continue
        at = _at(record)
        stats = sessions.get(session_id)
        if stats is None:
            sessions[session_id] = SessionStats(record.get("account_id"), at, at, 1)
            continue
        stats.started = min(stats.started, at)
        stats.ended = max(stats.ended, at)
        stats.events += 1
        if stats.account_id is None:
            stats.account_id = record.get("account_id")
    return sessions


def account_timeline(store: EventStore, account_id: str) -> list[tuple[datetime, str]]:
    """Every event of one account as (time, name), oldest first."""
    return sorted((_at(record), record["name"]) for record in store.for_account(account_id))
