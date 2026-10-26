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
    valid_low: float | None = None
    valid_high: float | None = None

    def apply(self, raw: float) -> float:
        return round((raw - self.offset) * self.gain, 3)

    def in_range(self, value: float) -> bool:
        if self.valid_low is not None and value < self.valid_low:
            return False
        if self.valid_high is not None and value > self.valid_high:
            return False
        return True


class CalibrationSource(Protocol):
    def load(self, sensor_id: str) -> Calibration: ...


Row = Mapping[str, Any]
QueryFn = Callable[[str, tuple[Any, ...]], list[Row]]

LATEST_CALIBRATION = (
    "SELECT raw_offset, gain, valid_low, valid_high FROM sensor_calibration "
    "WHERE sensor_id = ? ORDER BY calibrated_at DESC LIMIT 1"
)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


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
            valid_low=_optional_float(row["valid_low"]),
            valid_high=_optional_float(row["valid_high"]),
        )
