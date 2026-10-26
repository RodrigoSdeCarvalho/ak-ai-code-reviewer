import asyncio
import json

import pytest

from pipeline.cli import main
from pipeline.enrich import GeoTable, LookupTimeout
from pipeline.records import Event
from pipeline.runner import run

RANGES = {"10.0.0.0/8": "NL", "192.168.0.0/16": "BR"}


def _line(i: int, ip: str) -> str:
    return json.dumps({"id": f"e{i}", "user": f"u{i % 3}", "ip": ip, "path": "/pricing"})


LINES = [
    _line(1, "10.1.2.3"),
    "not json",
    _line(2, "192.168.4.5"),
    "",
    _line(3, "8.8.8.8"),
    _line(4, "10.9.9.9"),
    _line(5, "192.168.0.1"),
]


class FlakyGeo:
    """Times out on the first lookup of every address, then answers from a GeoTable."""

    def __init__(self) -> None:
        self._table = GeoTable(RANGES)
        self._seen: set[str] = set()

    async def country_for(self, ip: str) -> str:
        await asyncio.sleep(0)
        if ip not in self._seen:
            self._seen.add(ip)
            raise LookupTimeout(ip)
        return await self._table.country_for(ip)


def _run(lines, geo, **kwargs):
    out: list[Event] = []
    stats = asyncio.run(run(lines, geo, out.append, **kwargs))
    return stats, out


def test_timed_out_lookups_are_retried_into_real_events():
    stats, out = _run(LINES, FlakyGeo(), batch_size=2)
    assert all(isinstance(event, Event) for event in out)
    assert [event.country for event in out] == ["NL", "BR", "??", "NL", "BR"]
    assert stats.retried == 5


def test_streamed_input_is_processed_with_progress():
    seen: list[tuple[int, int]] = []
    stats, out = _run(iter(LINES), GeoTable(RANGES), batch_size=2, progress=lambda d, t: seen.append((d, t)))
    assert [event.event_id for event in out] == ["e1", "e2", "e3", "e4", "e5"]
    assert (stats.read, stats.skipped, stats.written) == (7, 2, 5)
    assert seen[-1] == (7, 7)


def test_cli_enriches_a_file(tmp_path):
    source, dest, ranges = tmp_path / "in.jsonl", tmp_path / "out.jsonl", tmp_path / "ranges.json"
    source.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    ranges.write_text(json.dumps(RANGES), encoding="utf-8")
    assert main([str(source), str(dest), "--ranges", str(ranges), "--concurrency", "2"]) == 0
    rows = [json.loads(line) for line in dest.read_text(encoding="utf-8").splitlines()]
    assert [(row["id"], row["country"]) for row in rows] == [
        ("e1", "NL"),
        ("e2", "BR"),
        ("e3", "??"),
        ("e4", "NL"),
        ("e5", "BR"),
    ]


def test_concurrency_must_be_positive():
    with pytest.raises(ValueError):
        asyncio.run(run(LINES, GeoTable(RANGES), lambda event: None, concurrency=0))
