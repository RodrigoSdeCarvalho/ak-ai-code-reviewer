"""Command line entry point: enrich a JSON-lines export into another JSON-lines file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pipeline.enrich import GeoTable
from pipeline.records import Event, to_json
from pipeline.runner import run


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="enrich-events")
    parser.add_argument("source", type=Path, help="JSON-lines export to read")
    parser.add_argument("dest", type=Path, help="where to write enriched JSON lines")
    parser.add_argument("--ranges", type=Path, required=True, help="JSON object of CIDR -> country")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    geo = GeoTable(json.loads(args.ranges.read_text(encoding="utf-8")))
    with (
        args.source.open(encoding="utf-8") as src,
        args.dest.open("w", encoding="utf-8") as dst,
    ):

        def sink(event: Event) -> None:
            dst.write(to_json(event) + "\n")

        stats = run(src, geo, sink)
    print(
        f"read={stats.read} skipped={stats.skipped} written={stats.written}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
