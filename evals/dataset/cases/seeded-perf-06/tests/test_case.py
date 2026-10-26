from datetime import datetime, timedelta

import pytest
from greenhouse.calibration import SqlCalibrationSource, UnknownSensor
from greenhouse.irrigation import IrrigationPolicy, format_plan, plan
from greenhouse.readings import Reading, summarize

CALIBRATIONS = {
    "s-a1": {"raw_offset": 100.0, "gain": 0.1, "valid_low": 0.0, "valid_high": 60.0},
    "s-a2": {"raw_offset": 120.0, "gain": 0.1, "valid_low": 0.0, "valid_high": 60.0},
    "s-b1": {"raw_offset": 0.0, "gain": 0.05, "valid_low": 5.0, "valid_high": None},
    "s-c1": {"raw_offset": 0.0, "gain": 1.0, "valid_low": 10.0, "valid_high": 20.0},
}
START = datetime(2026, 5, 4, 6, 0)


class CountingDb:
    def __init__(self) -> None:
        self.queries = 0

    def query(self, sql: str, params: tuple) -> list[dict]:
        self.queries += 1
        row = CALIBRATIONS.get(params[0])
        return [row] if row else []


def _reading(sensor: str, zone: str, minute: int, raw: float) -> Reading:
    return Reading(sensor, zone, START + timedelta(minutes=minute), raw)


def test_calibration_is_loaded_once_per_sensor_per_batch():
    db = CountingDb()
    readings = [
        _reading(sensor, zone, minute, 400.0)
        for minute in range(0, 24 * 60, 5)
        for sensor, zone in (("s-a1", "A"), ("s-a2", "A"), ("s-b1", "B"))
    ]
    summaries = summarize(readings, SqlCalibrationSource(db.query))
    assert summaries["A"].count == 2 * 288
    assert db.queries <= 3


def test_summary_applies_calibration_and_rejects_out_of_range_values():
    db = CountingDb()
    readings = [
        _reading("s-a1", "A", 0, 400.0),
        _reading("s-a2", "A", 1, 400.0),
        _reading("s-a1", "A", 2, 800.0),
        _reading("s-b1", "B", 0, 50.0),
        _reading("s-b1", "B", 1, 500.0),
        _reading("s-c1", "C", 0, 25.0),
    ]
    summaries = summarize(iter(readings), SqlCalibrationSource(db.query))
    a, b, c = summaries["A"], summaries["B"], summaries["C"]
    assert (a.count, a.rejected, a.mean, a.low, a.high) == (2, 1, 29.0, 28.0, 30.0)
    assert (b.count, b.rejected, b.mean) == (1, 1, 25.0)
    assert (c.count, c.rejected, c.mean, c.low) == (0, 1, None, None)
    assert b.rejected_share == 0.5


def test_unknown_sensor_is_reported():
    db = CountingDb()
    with pytest.raises(UnknownSensor):
        summarize([_reading("s-zz", "Z", 0, 1.0)], SqlCalibrationSource(db.query))


def test_irrigation_plan_waters_dry_zones_and_flags_faulty_ones():
    db = CountingDb()
    readings = [
        _reading("s-a1", "A", 0, 400.0),
        _reading("s-a2", "A", 1, 400.0),
        _reading("s-b1", "B", 0, 900.0),
        _reading("s-c1", "C", 0, 25.0),
    ]
    summaries = summarize(readings, SqlCalibrationSource(db.query))
    actions = plan(summaries, {"A": 40.0}, IrrigationPolicy(default_target=35.0, max_minutes=12))
    assert [(x.zone, x.action, x.minutes) for x in actions] == [
        ("A", "water", 12),
        ("B", "skip", 0),
        ("C", "inspect", 0),
    ]
    text = format_plan(actions)
    assert text.splitlines()[0].startswith("A  12 min")
