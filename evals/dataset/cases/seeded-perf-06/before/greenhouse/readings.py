from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean

from greenhouse.calibration import CalibrationSource


@dataclass(frozen=True)
class Reading:
    sensor_id: str
    zone: str
    taken_at: datetime
    raw: float


@dataclass(frozen=True)
class ZoneSummary:
    zone: str
    count: int
    mean: float
    low: float
    high: float


def _summary(zone: str, values: list[float]) -> ZoneSummary:
    return ZoneSummary(
        zone=zone,
        count=len(values),
        mean=round(fmean(values), 2),
        low=min(values),
        high=max(values),
    )


def summarize(readings: Iterable[Reading], source: CalibrationSource) -> dict[str, ZoneSummary]:
    batch = list(readings)
    calibrations = {sensor_id: source.load(sensor_id) for sensor_id in {r.sensor_id for r in batch}}
    by_zone: dict[str, list[float]] = defaultdict(list)
    for reading in batch:
        by_zone[reading.zone].append(calibrations[reading.sensor_id].apply(reading.raw))
    return {zone: _summary(zone, values) for zone, values in sorted(by_zone.items())}


def latest_per_sensor(readings: Iterable[Reading]) -> dict[str, Reading]:
    latest: dict[str, Reading] = {}
    for reading in readings:
        current = latest.get(reading.sensor_id)
        if current is None or reading.taken_at > current.taken_at:
            latest[reading.sensor_id] = reading
    return latest
