"""Batch jobs over device telemetry."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from telemetry.readings import Reading, read_lines
from telemetry.sessions import DEFAULT_MAX_GAP, Session, sessionize

MIN_CELSIUS = -60.0
MAX_CELSIUS = 125.0


@dataclass(frozen=True)
class DailyAverage:
    device_id: str
    day: date
    celsius: float
    samples: int


@dataclass(frozen=True)
class SessionReport:
    device_id: str
    sessions: int
    longest: timedelta
    samples: int


def plausible(reading: Reading) -> bool:
    """False for sensor glitches outside the hardware's measurable range (NaN included)."""
    return MIN_CELSIUS <= reading.celsius <= MAX_CELSIUS


def clean_readings(lines: Iterable[str], errors: list[str]) -> Iterator[Reading]:
    """Parsed, plausible readings; parse errors are appended to `errors` as the lines are consumed."""
    return (reading for reading in read_lines(lines, errors) if plausible(reading))


def daily_averages(readings: Iterable[Reading]) -> list[DailyAverage]:
    """Mean temperature per device per UTC day, sorted by device then day."""
    values_by_day: dict[tuple[str, date], list[float]] = defaultdict(list)
    for reading in readings:
        values_by_day[(reading.device_id, reading.taken_at.date())].append(reading.celsius)
    return [
        DailyAverage(device_id, day, round(sum(values) / len(values), 2), len(values))
        for (device_id, day), values in sorted(values_by_day.items())
    ]


def session_report(readings: Iterable[Reading], max_gap: timedelta = DEFAULT_MAX_GAP) -> list[SessionReport]:
    """Per device: how many recording sessions it had, the longest one and the samples they cover."""
    sessions_by_device: dict[str, list[Session]] = defaultdict(list)
    for session in sessionize(readings, max_gap):
        sessions_by_device[session.device_id].append(session)
    return [
        SessionReport(
            device_id=device_id,
            sessions=len(sessions),
            longest=max(session.duration for session in sessions),
            samples=sum(session.samples for session in sessions),
        )
        for device_id, sessions in sorted(sessions_by_device.items())
    ]


def run_daily_job(lines: Iterable[str]) -> tuple[list[DailyAverage], list[str]]:
    """Parse raw lines, drop implausible readings and aggregate per day. Returns the results and parse errors."""
    errors: list[str] = []
    results = daily_averages(clean_readings(lines, errors))
    return results, errors


def run_session_job(
    lines: Iterable[str], max_gap: timedelta = DEFAULT_MAX_GAP
) -> tuple[list[SessionReport], list[str]]:
    """Parse raw lines, drop implausible readings and report recording sessions per device."""
    errors: list[str] = []
    results = session_report(clean_readings(lines, errors), max_gap)
    return results, errors
