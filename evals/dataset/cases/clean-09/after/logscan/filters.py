"""Line filters for the logscan tool."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True)
class LogLine:
    timestamp: datetime
    level: str
    message: str


def parse(line: str) -> LogLine | None:
    """Split `<iso timestamp> <LEVEL> <message>`; None for lines that do not follow that format."""
    parts = line.rstrip("\n").split(" ", 2)
    if len(parts) < 3 or parts[1] not in LEVELS:
        return None
    try:
        timestamp = datetime.fromisoformat(parts[0])
    except ValueError:
        return None
    return LogLine(timestamp, parts[1], parts[2])


@dataclass(frozen=True)
class LogFilter:
    """Conditions a log line must meet; a condition left as None accepts everything."""

    since: datetime | None = None
    substring: str | None = None
    levels: frozenset[str] | None = None

    def accepts(self, entry: LogLine) -> bool:
        if self.since is not None and entry.timestamp < self.since:
            return False
        if self.levels is not None and entry.level not in self.levels:
            return False
        return self.substring is None or self.substring in entry.message

    def matching(self, lines: Iterable[str]) -> Iterator[str]:
        """Yield the raw lines that parse and pass every condition."""
        for line in lines:
            entry = parse(line)
            if entry is not None and self.accepts(entry):
                yield line
