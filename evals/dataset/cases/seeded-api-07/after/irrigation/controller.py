"""Drive the valves through a day's watering runs."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Protocol

from irrigation.config import Settings
from irrigation.scheduler import Run

log = logging.getLogger(__name__)


class Valve(Protocol):
    def open(self) -> None: ...

    def close(self) -> None: ...


class Controller:
    def __init__(
        self,
        settings: Settings,
        valves: Mapping[int, Valve],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        missing = [zone.name for zone in settings.zones if zone.valve not in valves]
        if missing:
            raise ValueError(f"no valve wired for zones: {', '.join(missing)}")
        self._settings = settings
        self._valves = valves
        self._sleep = sleep

    def water(self, runs: list[Run]) -> list[str]:
        """Open each zone's valve for its run, one zone at a time. Return the zones watered.

        Between two runs the controller waits `valve_gap_ms` so that line pressure settles before
        the next valve opens.
        """
        watered: list[str] = []
        gap_seconds = self._settings.valve_gap_ms / 1000
        for index, run in enumerate(runs):
            if index and gap_seconds:
                self._sleep(gap_seconds)
            self._run_zone(run)
            watered.append(run.zone.name)
        return watered

    def _run_zone(self, run: Run) -> None:
        valve = self._valves[run.zone.valve]
        log.info("watering %s for %.0fs", run.zone.name, run.seconds)
        valve.open()
        try:
            self._sleep(run.seconds)
        finally:
            valve.close()
