"""Parsing of raw device telemetry lines."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Reading:
    """One temperature sample reported by a device."""

    device_id: str
    taken_at: datetime
    celsius: float


class MalformedLine(ValueError):
    """A telemetry line could not be parsed."""


def parse_line(line: str) -> Reading:
    """Parse `device_id,iso_timestamp,celsius` into a Reading with a UTC timestamp."""
    parts = [part.strip() for part in line.split(",")]
    if len(parts) != 3 or not parts[0]:
        raise MalformedLine(f"expected 3 fields: {line!r}")
    device_id, raw_ts, raw_value = parts
    try:
        taken_at = datetime.fromisoformat(raw_ts)
        celsius = float(raw_value)
    except ValueError as exc:
        raise MalformedLine(f"bad field in {line!r}") from exc
    if taken_at.tzinfo is None:
        taken_at = taken_at.replace(tzinfo=UTC)
    return Reading(device_id, taken_at.astimezone(UTC), celsius)


def read_lines(lines: Iterable[str], errors: list[str] | None = None) -> Iterator[Reading]:
    """Yield parsed readings, skipping blank lines and comments; malformed lines are reported to `errors`."""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            yield parse_line(stripped)
        except MalformedLine as exc:
            if errors is not None:
                errors.append(str(exc))
