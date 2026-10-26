"""Command-line entry point: `python -m metering.cli <command> <export.csv>`."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from metering.events import EventFormatError, UsageEvent, load_events


def read_events(path: Path) -> list[UsageEvent]:
    with path.open(encoding="utf-8") as handle:
        return list(load_events(handle))


def summarize(events: Sequence[UsageEvent]) -> dict[str, dict[str, int]]:
    """Total quantity per account and metric."""
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        totals[event.account_id][event.metric] += event.quantity
    return {account: dict(metrics) for account, metrics in totals.items()}


def _cmd_summary(args: argparse.Namespace) -> int:
    for account, metrics in sorted(summarize(read_events(args.export)).items()):
        parts = ", ".join(f"{metric}={value}" for metric, value in sorted(metrics.items()))
        print(f"{account}: {parts}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metering")
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary", help="total usage per account")
    summary.add_argument("export", type=Path)
    summary.set_defaults(handler=_cmd_summary)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, EventFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
