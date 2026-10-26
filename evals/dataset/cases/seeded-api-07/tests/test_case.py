from datetime import date, time

import pytest

from irrigation.config import ConfigError, parse_duration, parse_settings
from irrigation.controller import Controller
from irrigation.scheduler import plan_day


class RecordingValve:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events

    def open(self) -> None:
        self.events.append(f"open {self.name}")

    def close(self) -> None:
        self.events.append(f"close {self.name}")


def _settings():
    return parse_settings(
        {
            "valve_gap": "750ms",
            "zones": [
                {"name": "lawn", "valve": 1, "start": "06:00", "duration": "10m"},
                {"name": "beds", "valve": 2, "start": "06:00", "minutes": 5, "days": ["mon", "thu"]},
                {"name": "hedge", "valve": 3, "start": "21:30", "duration": "1h30m", "rain_skip_mm": 4},
            ],
        }
    )


def test_parse_duration():
    assert parse_duration("750ms") == 750
    assert parse_duration("1h 30m") == 5_400_000
    assert parse_duration("2.5s") == 2_500
    for bad in ["", "10", "5 minutes", "m10"]:
        with pytest.raises(ConfigError):
            parse_duration(bad)


def test_plan_uses_configured_run_lengths():
    runs = plan_day(_settings(), date(2026, 6, 1))
    assert [(r.zone.name, r.start.time(), r.end.time()) for r in runs] == [
        ("beds", time(6, 0), time(6, 5)),
        ("lawn", time(6, 5), time(6, 15)),
        ("hedge", time(21, 30), time(23, 0)),
    ]
    assert [r.zone.name for r in plan_day(_settings(), date(2026, 6, 2), rain_mm=5)] == ["lawn"]


def test_controller_keeps_each_valve_open_for_its_run():
    settings = _settings()
    events: list[str] = []
    sleeps: list[float] = []
    valves = {n: RecordingValve(str(n), events) for n in (1, 2, 3)}
    controller = Controller(settings, valves, sleep=sleeps.append)
    watered = controller.water(plan_day(settings, date(2026, 6, 4)))
    assert watered == ["beds", "lawn", "hedge"]
    assert sleeps == [300.0, 0.75, 600.0, 0.75, 5400.0]
    assert events == ["open 2", "close 2", "open 1", "close 1", "open 3", "close 3"]


def test_invalid_zone_is_rejected():
    with pytest.raises(ConfigError):
        parse_settings({"zones": [{"name": "lawn", "valve": 1, "duration": "0s"}]})
    with pytest.raises(ConfigError):
        parse_settings({"zones": [{"name": "lawn", "valve": 1, "duration": "ten minutes"}]})
