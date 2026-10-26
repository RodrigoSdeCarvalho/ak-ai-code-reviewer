"""Public-holiday data maintained by the operations team, per region."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Protocol


class UnknownRegion(KeyError):
    """Raised when no holiday data exists for a region code."""


class HolidaySource(Protocol):
    def holidays(self, region: str, year: int) -> Iterable[date]: ...


class JsonHolidaySource:
    """Holidays from a JSON file shaped like `{"PT": {"2026": ["2026-01-01", ...]}, ...}`."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def holidays(self, region: str, year: int) -> list[date]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if region not in data:
            raise UnknownRegion(region)
        return [date.fromisoformat(raw) for raw in data[region].get(str(year), [])]


class StaticHolidaySource:
    """Fixed holidays per region, for tests and local development."""

    def __init__(self, days: Mapping[str, Iterable[date]]) -> None:
        self._days = {region: sorted(set(values)) for region, values in days.items()}

    def holidays(self, region: str, year: int) -> list[date]:
        if region not in self._days:
            raise UnknownRegion(region)
        return [day for day in self._days[region] if day.year == year]


def write_holiday_file(path: Path, days: Mapping[str, Iterable[date]]) -> None:
    data: dict[str, dict[str, list[str]]] = {}
    for region, values in sorted(days.items()):
        by_year = data.setdefault(region, {})
        for day in sorted(set(values)):
            by_year.setdefault(str(day.year), []).append(day.isoformat())
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
