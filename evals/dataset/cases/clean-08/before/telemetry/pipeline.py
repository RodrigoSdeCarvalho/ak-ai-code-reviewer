"""Batch jobs over device telemetry."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from telemetry.readings import Reading, read_lines

MIN_CELSIUS = -60.0
MAX_CELSIUS = 125.0


@dataclass(frozen=True)
class DailyAverage:
    device_id: str
    day: date
    celsius: float
    samples: int


def plausible(reading: Reading) -> bool:
    """False for sensor glitches outside the hardware's measurable range (NaN included)."""
    return MIN_CELSIUS <= reading.celsius <= MAX_CELSIUS


def daily_averages(readings: Iterable[Reading]) -> list[DailyAverage]:
    """Mean temperature per device per UTC day, sorted by device then day."""
    values_by_day: dict[tuple[str, date], list[float]] = defaultdict(list)
    for reading in readings:
        values_by_day[(reading.device_id, reading.taken_at.date())].append(reading.celsius)
    return [
        DailyAverage(device_id, day, round(sum(values) / len(values), 2), len(values))
        for (device_id, day), values in sorted(values_by_day.items())
    ]


def run_daily_job(lines: Iterable[str]) -> tuple[list[DailyAverage], list[str]]:
    """Parse raw lines, drop implausible readings and aggregate per day. Returns the results and parse errors."""
    errors: list[str] = []
    readings = (reading for reading in read_lines(lines, errors) if plausible(reading))
    return daily_averages(readings), errors
