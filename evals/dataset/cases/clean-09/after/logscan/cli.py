"""Command-line entry point: print the lines of application log files that match the given options."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import datetime

from logscan.filters import LEVELS, LogFilter


def _timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO timestamp: {value!r}") from None


def _count(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {value!r}") from None
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or more")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="logscan", description="Print matching lines from log files.")
    parser.add_argument("paths", nargs="+", help="log files to scan, in order")
    parser.add_argument("--since", type=_timestamp, help="only lines at or after this ISO timestamp")
    parser.add_argument("--grep", help="only lines whose message contains this text")
    parser.add_argument("--level", dest="levels", action="append", choices=LEVELS, help="only this level; repeatable")
    parser.add_argument("--limit", type=_count, help="stop after printing this many lines across all files")
    return parser


def filter_from_args(args: argparse.Namespace) -> LogFilter:
    levels = frozenset(args.levels) if args.levels else None
    return LogFilter(since=args.since, substring=args.grep, levels=levels)


def _emit(line: str) -> None:
    sys.stdout.write(line if line.endswith("\n") else line + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_filter = filter_from_args(args)
    if args.limit == 0:
        return 0
    printed = 0
    for path in args.paths:
        try:
            with open(path, encoding="utf-8") as handle:
                for line in log_filter.matching(handle):
                    _emit(line)
                    printed += 1
                    if printed == args.limit:
                        return 0
        except OSError as exc:
            print(f"logscan: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
