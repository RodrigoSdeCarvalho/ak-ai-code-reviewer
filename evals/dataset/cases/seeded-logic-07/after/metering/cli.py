"""Command-line entry point: `python -m metering.cli <command> <export.csv>`."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from metering.events import EventFormatError, UsageEvent, load_events
from metering.report import build_report, render_csv, render_text
from metering.rollup import rollup

MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def read_events(path: Path) -> list[UsageEvent]:
    with path.open(encoding="utf-8") as handle:
        return list(load_events(handle))


def summarize(events: Sequence[UsageEvent]) -> dict[str, dict[str, int]]:
    """Total quantity per account and metric."""
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for event in events:
        totals[event.account_id][event.metric] += event.quantity
    return {account: dict(metrics) for account, metrics in totals.items()}


def month_arg(value: str) -> str:
    if not MONTH_RE.match(value):
        raise argparse.ArgumentTypeError(f"expected YYYY-MM, got {value!r}")
    return value


def _cmd_summary(args: argparse.Namespace) -> int:
    for account, metrics in sorted(summarize(read_events(args.export)).items()):
        parts = ", ".join(f"{metric}={value}" for metric, value in sorted(metrics.items()))
        print(f"{account}: {parts}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    rows = build_report(rollup(read_events(args.export)), args.month)
    output = render_csv(rows) if args.format == "csv" else render_text(rows, args.month)
    sys.stdout.write(output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metering")
    commands = parser.add_subparsers(dest="command", required=True)
    summary = commands.add_parser("summary", help="total usage per account")
    summary.add_argument("export", type=Path)
    summary.set_defaults(handler=_cmd_summary)
    report = commands.add_parser("report", help="monthly usage report with month-over-month change")
    report.add_argument("export", type=Path)
    report.add_argument("--month", type=month_arg, required=True, help="YYYY-MM")
    report.add_argument("--format", choices=("text", "csv"), default="text")
    report.set_defaults(handler=_cmd_report)
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
