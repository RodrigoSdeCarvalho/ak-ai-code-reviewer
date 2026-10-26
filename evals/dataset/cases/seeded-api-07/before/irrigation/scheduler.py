"""Turn the zone configuration into the watering runs for one day."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from irrigation.config import Settings, ZoneConfig


@dataclass(frozen=True)
class Run:
    zone: ZoneConfig
    start: datetime
    end: datetime

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()


def plan_day(settings: Settings, day: date, rain_mm: float = 0.0) -> list[Run]:
    """Return the runs for `day` in start order.

    Zones that share a start time run one after another, because the pump can only feed one valve
    at a time. A zone is skipped when the rain measured for the day reaches its threshold.
    """
    due = sorted(
        (zone for zone in settings.zones if day.weekday() in zone.days),
        key=lambda zone: (zone.start, zone.name),
    )
    runs: list[Run] = []
    pump_free_at: datetime | None = None
    for zone in due:
        if zone.rain_skip_mm is not None and rain_mm >= zone.rain_skip_mm:
            continue
        start = datetime.combine(day, zone.start)
        if pump_free_at is not None and pump_free_at > start:
            start = pump_free_at
        end = start + timedelta(seconds=zone.duration)
        runs.append(Run(zone, start, end))
        pump_free_at = end
    return runs


def litres(runs: Iterable[Run], flow_l_per_min: dict[str, float]) -> float:
    """Estimate the water used by `runs`, given each zone's flow rate in litres per minute."""
    return sum(run.seconds / 60 * flow_l_per_min.get(run.zone.name, 0.0) for run in runs)


def finishes_by(runs: list[Run], deadline: datetime) -> bool:
    return not runs or runs[-1].end <= deadline
