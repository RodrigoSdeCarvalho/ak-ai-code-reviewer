"""Load the irrigation controller configuration from its JSON document."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


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

    def zone(self, name: str) -> ZoneConfig:
        for zone in self.zones:
            if zone.name == name:
                return zone
        raise KeyError(name)


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
        minutes = float(entry["minutes"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(f"invalid zone entry {entry!r}") from exc
    if minutes <= 0:
        raise ConfigError(f"zone {name!r}: minutes must be positive")
    rain = entry.get("rain_skip_mm")
    return ZoneConfig(
        name=name,
        valve=valve,
        start=_parse_start(str(entry.get("start", "06:00"))),
        duration=minutes * 60,
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
    return Settings(zones=zones, timezone=str(document.get("timezone", "UTC")))


def load_settings(path: Path) -> Settings:
    return parse_settings(json.loads(path.read_text(encoding="utf-8")))
