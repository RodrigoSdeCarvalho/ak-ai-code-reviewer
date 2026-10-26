"""Batch job: parse exported events, add the visitor country, hand them to a sink."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

from pipeline.enrich import GeoClient, LookupTimeout, enrich
from pipeline.records import Event, parse_line

Sink = Callable[[Event], None]
Progress = Callable[[int, int], None]


@dataclass
class RunStats:
    read: int = 0
    skipped: int = 0
    written: int = 0
    retried: int = 0


async def run(
    lines: Iterable[str],
    geo: GeoClient,
    sink: Sink,
    *,
    concurrency: int = 16,
    batch_size: int = 500,
    progress: Progress | None = None,
) -> RunStats:
    """Enrich every parseable line and pass it to `sink`, in input order.

    Lookups run concurrently (at most `concurrency` in flight); a lookup that times out is
    retried once, and a second timeout aborts the run. `progress(lines_read, total_lines)` is
    called after each batch.
    """
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    stats = RunStats()
    lines = list(lines)
    total = len(lines)
    semaphore = asyncio.Semaphore(concurrency)

    async def enrich_one(event: Event) -> Event:
        async with semaphore:
            try:
                return await enrich(event, geo)
            except LookupTimeout:
                stats.retried += 1
                return await enrich(event, geo)

    batch: list[Event] = []
    for line in lines:
        stats.read += 1
        event = parse_line(line)
        if event is None:
            stats.skipped += 1
            continue
        batch.append(event)
        if len(batch) >= batch_size:
            await _flush(batch, enrich_one, sink, stats)
            batch = []
            if progress is not None:
                progress(stats.read, total)
    if batch:
        await _flush(batch, enrich_one, sink, stats)
    if progress is not None:
        progress(stats.read, total)
    return stats


async def _flush(
    batch: list[Event],
    enrich_one: Callable[[Event], Awaitable[Event]],
    sink: Sink,
    stats: RunStats,
) -> None:
    for event in await asyncio.gather(*(enrich_one(event) for event in batch)):
        sink(event)
        stats.written += 1
