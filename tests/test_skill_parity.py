"""SKILL.md embeds the current default prompt byte-for-byte, so the skill and the API reviewer cannot drift."""

from __future__ import annotations

import re

import yaml

from aireview.reviewer.claude_cli import SKILL_PATH, skill_prompt
from aireview.reviewer.reviewer import load_config, load_prompt
from aireview.settings import repo_root

MARKER_RE = re.compile(r"<!-- prompt:(?P<version>[^ ]+) -->")


def _default_version() -> str:
    version = load_config(repo_root() / "evals" / "configs" / "v1-sonnet.yaml").prompt_version
    assert version is not None
    return version


def test_skill_body_equals_default_prompt() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    marker = MARKER_RE.search(text)
    assert marker is not None, "SKILL.md needs a '<!-- prompt:<version> -->' marker line"
    assert marker.group("version") == _default_version()
    body = text[marker.end() : text.index("## Running headless")]
    assert body.strip() == load_prompt(_default_version()).strip()
    assert skill_prompt() == (_default_version(), body.strip())


def test_skill_frontmatter() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = yaml.safe_load(text.split("---\n", 2)[1])
    assert front["name"] == "aireview-code-review"
    assert SKILL_PATH.parent.name == front["name"]  # the directory name is the skill name
    assert "findings" in front["description"]


def test_headless_section_matches_cli_flags() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    headless = text[text.index("## Running headless") :]
    for flag in (
        "claude -p --bare",
        "--output-format json",
        "--json-schema",
        "--no-session-persistence",
        "--max-budget-usd 1",
        '--tools ""',
    ):
        assert flag in headless
    assert "--max-turns" not in headless  # not a flag of the installed Claude Code CLI
    assert "aireview review" in headless
