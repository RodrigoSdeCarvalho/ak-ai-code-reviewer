"""Load the irrigation controller configuration from its JSON document."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_UNIT_MS = {"ms": 1, "s": 1_000, "m": 60_000, "h": 3_600_000}
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ZoneConfig:
    name: str
    valve: int
    start: time
    duration: float
    days: frozenset[int]
    rain_skip_mm: float | None = None


@dataclass(frozen=True)
class Settings:
    zones: tuple[ZoneConfig, ...]
    timezone: str = "UTC"
    valve_gap_ms: int = 0

    def zone(self, name: str) -> ZoneConfig:
        for zone in self.zones:
            if zone.name == name:
                return zone
        raise KeyError(name)


def parse_duration(text: str) -> int:
    """Parse a duration such as "45s", "10m", "1h30m" or "750ms" and return it in milliseconds."""
    compact = text.replace(" ", "").lower()
    parts = _DURATION_PART.findall(compact)
    if not parts or "".join(number + unit for number, unit in parts) != compact:
        raise ConfigError(f"invalid duration {text!r}")
    return round(sum(float(number) * _UNIT_MS[unit] for number, unit in parts))


def _parse_days(raw: Any) -> frozenset[int]:
    if raw == "daily":
        return frozenset(range(7))
    try:
        return frozenset(WEEKDAYS.index(str(day).lower()[:3]) for day in raw)
    except ValueError as exc:
        raise ConfigError(f"unknown weekday in {raw!r}") from exc


def _parse_start(raw: str) -> time:
    try:
        hours, minutes = raw.split(":")
        return time(int(hours), int(minutes))
    except ValueError as exc:
        raise ConfigError(f"start must be HH:MM, got {raw!r}") from exc


def _parse_zone(entry: dict[str, Any]) -> ZoneConfig:
    try:
        name = str(entry["name"])
        valve = int(entry["valve"])
        if "duration" in entry:
            run_time = parse_duration(str(entry["duration"]))
        else:
            run_time = parse_duration(f"{float(entry['minutes'])}m")
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid zone entry {entry!r}") from exc
    if run_time <= 0:
        raise ConfigError(f"zone {name!r}: duration must be positive")
    rain = entry.get("rain_skip_mm")
    return ZoneConfig(
        name=name,
        valve=valve,
        start=_parse_start(str(entry.get("start", "06:00"))),
        duration=run_time / 1000,
        days=_parse_days(entry.get("days", "daily")),
        rain_skip_mm=None if rain is None else float(rain),
    )


def parse_settings(document: dict[str, Any]) -> Settings:
    zones = tuple(_parse_zone(entry) for entry in document.get("zones", []))
    names = [zone.name for zone in zones]
    if len(set(names)) != len(names):
        raise ConfigError("zone names must be unique")
    valves = [zone.valve for zone in zones]
    if len(set(valves)) != len(valves):
        raise ConfigError("each zone needs its own valve")
    return Settings(
        zones=zones,
        timezone=str(document.get("timezone", "UTC")),
        valve_gap_ms=parse_duration(str(document.get("valve_gap", "0ms"))),
    )


def load_settings(path: Path) -> Settings:
    return parse_settings(json.loads(path.read_text(encoding="utf-8")))
