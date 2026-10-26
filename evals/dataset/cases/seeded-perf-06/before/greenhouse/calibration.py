from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class UnknownSensor(LookupError):
    pass


@dataclass(frozen=True)
class Calibration:
    sensor_id: str
    offset: float
    gain: float

    def apply(self, raw: float) -> float:
        return round((raw - self.offset) * self.gain, 3)


class CalibrationSource(Protocol):
    def load(self, sensor_id: str) -> Calibration: ...


Row = Mapping[str, Any]
QueryFn = Callable[[str, tuple[Any, ...]], list[Row]]

LATEST_CALIBRATION = (
    "SELECT raw_offset, gain FROM sensor_calibration "
    "WHERE sensor_id = ? ORDER BY calibrated_at DESC LIMIT 1"
)


class SqlCalibrationSource:
    def __init__(self, query: QueryFn) -> None:
        self._query = query

    def load(self, sensor_id: str) -> Calibration:
        rows = self._query(LATEST_CALIBRATION, (sensor_id,))
        if not rows:
            raise UnknownSensor(sensor_id)
        row = rows[0]
        return Calibration(
            sensor_id=sensor_id,
            offset=float(row["raw_offset"]),
            gain=float(row["gain"]),
        )
