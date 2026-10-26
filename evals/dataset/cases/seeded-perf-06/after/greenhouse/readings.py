from __future__ import annotations

from collections import Counter, defaultdict
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
    rejected: int
    mean: float | None
    low: float | None
    high: float | None

    @property
    def rejected_share(self) -> float:
        total = self.count + self.rejected
        return self.rejected / total if total else 0.0


def _summary(zone: str, values: list[float], rejected: int) -> ZoneSummary:
    if not values:
        return ZoneSummary(zone=zone, count=0, rejected=rejected, mean=None, low=None, high=None)
    return ZoneSummary(
        zone=zone,
        count=len(values),
        rejected=rejected,
        mean=round(fmean(values), 2),
        low=min(values),
        high=max(values),
    )


def calibrated(reading: Reading, source: CalibrationSource) -> float | None:
    calibration = source.load(reading.sensor_id)
    value = calibration.apply(reading.raw)
    return value if calibration.in_range(value) else None


def summarize(readings: Iterable[Reading], source: CalibrationSource) -> dict[str, ZoneSummary]:
    accepted: dict[str, list[float]] = defaultdict(list)
    rejected: Counter[str] = Counter()
    for reading in readings:
        value = calibrated(reading, source)
        if value is None:
            rejected[reading.zone] += 1
        else:
            accepted[reading.zone].append(value)
    zones = sorted(set(accepted) | set(rejected))
    return {zone: _summary(zone, accepted.get(zone, []), rejected[zone]) for zone in zones}


def latest_per_sensor(readings: Iterable[Reading]) -> dict[str, Reading]:
    latest: dict[str, Reading] = {}
    for reading in readings:
        current = latest.get(reading.sensor_id)
        if current is None or reading.taken_at > current.taken_at:
            latest[reading.sensor_id] = reading
    return latest
