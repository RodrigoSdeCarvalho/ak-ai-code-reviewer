"""Public-holiday data maintained by the operations team."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Protocol


class HolidaySource(Protocol):
    def holidays(self, year: int) -> Iterable[date]: ...


class JsonHolidaySource:
    """Holidays from a JSON file shaped like `{"2026": ["2026-01-01", ...]}`."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def holidays(self, year: int) -> list[date]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return [date.fromisoformat(raw) for raw in data.get(str(year), [])]


class StaticHolidaySource:
    """Fixed list of holidays, for tests and local development."""

    def __init__(self, days: Iterable[date]) -> None:
        self._days = sorted(set(days))

    def holidays(self, year: int) -> list[date]:
        return [day for day in self._days if day.year == year]


def write_holiday_file(path: Path, days: Iterable[date]) -> None:
    by_year: dict[str, list[str]] = {}
    for day in sorted(set(days)):
        by_year.setdefault(str(day.year), []).append(day.isoformat())
    path.write_text(json.dumps(by_year, indent=2), encoding="utf-8")
