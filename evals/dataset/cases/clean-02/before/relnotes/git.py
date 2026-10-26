"""Read commit subjects from git for the release-notes generator."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

FIELD_SEP = "\x1f"
LOG_FORMAT = f"--format=%h{FIELD_SEP}%an{FIELD_SEP}%s"


class GitError(RuntimeError):
    """git exited with a non-zero status."""


@dataclass(frozen=True)
class Commit:
    short_sha: str
    author: str
    subject: str


def parse_log(output: str) -> list[Commit]:
    """Parse `git log` output produced with LOG_FORMAT."""
    commits: list[Commit] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        sha, author, subject = line.split(FIELD_SEP, 2)
        commits.append(Commit(short_sha=sha, author=author, subject=subject))
    return commits


def commits_between(repo: Path, since: str, until: str = "HEAD") -> list[Commit]:
    """Non-merge commits reachable from `until` but not from `since`, oldest first."""
    argv = ["git", "log", "--no-merges", "--reverse", LOG_FORMAT, f"{since}..{until}"]
    try:
        proc = subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise GitError(exc.stderr.strip() or f"git log exited with {exc.returncode}") from exc
    return parse_log(proc.stdout)
