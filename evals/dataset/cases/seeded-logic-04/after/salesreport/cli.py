"""`salesreport daily EXPORT.csv [--store NAME] [--since DAY] [--until DAY]`: print daily totals."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import TextIO

from salesreport.daily import daily_totals, format_report
from salesreport.records import RecordError, read_sales


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="salesreport")
    sub = parser.add_subparsers(dest="command", required=True)
    daily = sub.add_parser("daily", help="daily totals")
    daily.add_argument("export", type=Path)
    daily.add_argument("--store", default=None, help="only this store")
    daily.add_argument("--since", type=date.fromisoformat, default=None, help="first day (default: first sale)")
    daily.add_argument("--until", type=date.fromisoformat, default=None, help="last day (default: last sale)")
    return parser


def run_daily(args: argparse.Namespace, out: TextIO) -> int:
    with args.export.open(encoding="utf-8", newline="") as handle:
        sales = list(read_sales(handle))
    if not sales and (args.since is None or args.until is None):
        out.write("no sales in export\n")
        return 0
    since = args.since or min(sale.day for sale in sales)
    until = args.until or max(sale.day for sale in sales)
    rows = daily_totals(sales, since, until, args.store)
    out.write(format_report(rows) + "\n")
    return 0


def main(argv: Sequence[str] | None = None, out: TextIO = sys.stdout) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_daily(args, out)
    except RecordError as exc:
        print(f"{args.export}: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"salesreport: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"cannot read {args.export}: {exc.strerror}", file=sys.stderr)
        return 2
