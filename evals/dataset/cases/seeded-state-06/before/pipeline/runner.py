"""Batch job: parse exported events, add the visitor country, hand them to a sink."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from pipeline.enrich import GeoTable, enrich
from pipeline.records import Event, parse_line

Sink = Callable[[Event], None]


@dataclass
class RunStats:
    read: int = 0
    skipped: int = 0
    written: int = 0


def run(lines: Iterable[str], geo: GeoTable, sink: Sink) -> RunStats:
    """Enrich every parseable line and pass it to `sink`, in input order."""
    stats = RunStats()
    for line in lines:
        stats.read += 1
        event = parse_line(line)
        if event is None:
            stats.skipped += 1
            continue
        sink(enrich(event, geo))
        stats.written += 1
    return stats
