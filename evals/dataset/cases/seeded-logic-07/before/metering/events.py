"""Usage events exported by the API gateway, one CSV line per metered call batch."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

METRICS = frozenset({"api_calls", "storage_gb", "egress_gb"})


class EventFormatError(ValueError):
    """A line in the usage export could not be parsed."""


@dataclass(frozen=True)
class UsageEvent:
    account_id: str
    metric: str
    quantity: int
    timestamp: datetime


def parse_line(line: str) -> UsageEvent:
    """Parse `account_id,metric,quantity,iso_timestamp`; naive timestamps are taken as UTC."""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 4:
        raise EventFormatError(f"expected 4 fields, got {len(parts)}: {line!r}")
    account_id, metric, raw_quantity, raw_timestamp = parts
    if not account_id:
        raise EventFormatError(f"missing account id: {line!r}")
    if metric not in METRICS:
        raise EventFormatError(f"unknown metric {metric!r}")
    try:
        quantity = int(raw_quantity)
        timestamp = datetime.fromisoformat(raw_timestamp)
    except ValueError as exc:
        raise EventFormatError(f"bad quantity or timestamp: {line!r}") from exc
    if quantity < 0:
        raise EventFormatError(f"negative quantity: {line!r}")
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return UsageEvent(account_id, metric, quantity, timestamp.astimezone(UTC))


def load_events(lines: Iterable[str]) -> Iterator[UsageEvent]:
    """Parse every non-blank line that is not a `#` comment."""
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield parse_line(stripped)
