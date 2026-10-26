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
        """Open each zone's valve for its run, one zone at a time. Return the zones watered."""
        watered: list[str] = []
        for run in runs:
            valve = self._valves[run.zone.valve]
            log.info("watering %s for %.0fs", run.zone.name, run.seconds)
            valve.open()
            try:
                self._sleep(run.seconds)
            finally:
                valve.close()
            watered.append(run.zone.name)
        return watered
