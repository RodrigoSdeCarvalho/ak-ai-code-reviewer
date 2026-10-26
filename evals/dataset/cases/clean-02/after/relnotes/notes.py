"""Group commits into release-note sections and render them as Markdown."""

from __future__ import annotations

import re
from collections.abc import Iterable

from relnotes.git import Commit

SECTIONS: tuple[tuple[str, str], ...] = (
    ("feat", "Features"),
    ("fix", "Fixes"),
    ("perf", "Performance"),
    ("docs", "Documentation"),
)
OTHER_SECTION = "Other changes"
_PREFIX = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?!?:\s*(?P<text>.+)$")


def classify(subject: str) -> tuple[str, str]:
    """Section title and display text for a commit subject in conventional-commit form."""
    match = _PREFIX.match(subject)
    if match is None:
        return OTHER_SECTION, subject
    for prefix, title in SECTIONS:
        if match["type"] == prefix:
            return title, match["text"]
    return OTHER_SECTION, match["text"]


def group(commits: Iterable[Commit]) -> dict[str, list[str]]:
    """Section title to bullet lines, in SECTIONS order, empty sections left out."""
    order = [title for _, title in SECTIONS] + [OTHER_SECTION]
    buckets: dict[str, list[str]] = {title: [] for title in order}
    for commit in commits:
        title, text = classify(commit.subject)
        buckets[title].append(f"{text} ({commit.short_sha})")
    return {title: lines for title, lines in buckets.items() if lines}


def render(version: str, commits: Iterable[Commit]) -> str:
    """Markdown release notes for `version`."""
    out = [f"## {version}", ""]
    for title, lines in group(commits).items():
        out.append(f"### {title}")
        out.extend(f"- {line}" for line in lines)
        out.append("")
    return "\n".join(out).rstrip() + "\n"
