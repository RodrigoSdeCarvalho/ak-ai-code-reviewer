"""`relnotes` command line: print Markdown release notes for a revision range."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from relnotes.git import GitError, commits_between
from relnotes.notes import render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relnotes", description=__doc__)
    parser.add_argument("version", help="version heading for the notes, e.g. 2.4.0")
    parser.add_argument("--since", required=True, help="previous release tag or commit")
    parser.add_argument("--until", default="HEAD", help="last commit to include (default: HEAD)")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="repository directory")
    parser.add_argument("--output", type=Path, help="write to this file instead of stdout")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        commits = commits_between(args.repo, args.since, args.until)
    except GitError as exc:
        print(f"relnotes: git failed: {exc}", file=sys.stderr)
        return 2
    if not commits:
        print(f"relnotes: no commits in {args.since}..{args.until}", file=sys.stderr)
        return 1
    text = render(args.version, commits)
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
