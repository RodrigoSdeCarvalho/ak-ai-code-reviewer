"""Headless Claude Code backend: runs the `aireview-code-review` skill text through `claude -p --bare`.

`--bare` does not load skills, so the skill body itself is sent: the skill text and the review context go
in on stdin, and `--json-schema` makes the CLI return the findings as `structured_output` in its JSON
envelope. `--no-session-persistence` keeps eval runs out of the session history and `--max-budget-usd`
caps one review's spend. The subprocess call is injectable so tests never run `claude`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aireview.evals.schema import ReviewerConfig
from aireview.models import Review, ReviewOutput, ReviewStatus, Usage
from aireview.reviewer.context import build_user_message
from aireview.reviewer.reviewer import (
    DEFAULT_PROMPT_VERSION,
    failed_review,
    load_prompt,
    resolve_config,
    review_from_output,
)
from aireview.settings import DEFAULT_REVIEWER_MODEL, repo_root

SKILL_NAME = "aireview-code-review"  # not `code-review`: that name is a built-in Claude Code skill
SKILL_PATH = repo_root() / "skills" / SKILL_NAME / "SKILL.md"
PROMPT_MARKER_PREFIX = "<!-- prompt:"
HEADLESS_HEADING = "## Running headless"
MAX_BUDGET_USD = 1
TIMEOUT_S = 600.0


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[list[str], str, float], RunResult]


def run_subprocess(argv: list[str], stdin: str, timeout_s: float) -> RunResult:
    """Run `argv` with `stdin` as input (list form, no shell)."""
    proc = subprocess.run(
        argv, input=stdin, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout_s, check=False
    )
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


def skill_prompt(path: Path = SKILL_PATH) -> tuple[str, str]:
    """(prompt version, prompt text) embedded in SKILL.md between the marker and the headless section."""
    text = path.read_text(encoding="utf-8")
    start = text.index(PROMPT_MARKER_PREFIX)
    marker_end = text.index("-->", start)
    version = text[start + len(PROMPT_MARKER_PREFIX) : marker_end].strip()
    body = text[marker_end + len("-->") : text.index(HEADLESS_HEADING, marker_end)]
    return version, body.strip()


def _skill_text(config: ReviewerConfig) -> str:
    """The skill body when it holds the configured prompt version, else the prompt file itself."""
    version = config.prompt_version or DEFAULT_PROMPT_VERSION
    if SKILL_PATH.is_file():
        skill_version, body = skill_prompt()
        if skill_version == version:
            return body
    return load_prompt(version).strip()


def build_argv(config: ReviewerConfig, executable: str = "claude") -> list[str]:
    """`claude -p --bare ...` argv; the schema is a single argv element and all tools are disabled."""
    argv = [
        executable,
        "-p",
        "--bare",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(ReviewOutput.model_json_schema(), separators=(",", ":")),
        "--model",
        config.model or DEFAULT_REVIEWER_MODEL,
        "--no-session-persistence",
        "--max-budget-usd",
        str(MAX_BUDGET_USD),
    ]
    if config.effort:
        argv += ["--effort", config.effort]
    return [*argv, "--tools", ""]


def _usage(envelope: dict[str, Any]) -> Usage:
    tokens = envelope.get("usage") or {}
    duration = envelope.get("duration_ms")
    return Usage(
        input_tokens=int(tokens.get("input_tokens") or 0),
        output_tokens=int(tokens.get("output_tokens") or 0),
        cache_read_input_tokens=int(tokens.get("cache_read_input_tokens") or 0),
        cache_creation_input_tokens=int(tokens.get("cache_creation_input_tokens") or 0),
        cost_usd=float(envelope.get("total_cost_usd") or 0.0),
        latency_ms=int(duration) if duration is not None else None,
    )


def parse_envelope(result: RunResult, diff_text: str, config: ReviewerConfig) -> Review:
    """Map the CLI's JSON envelope to a `Review`."""
    try:
        envelope = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = (result.stderr or result.stdout).strip()[-500:]
        return failed_review(config, ReviewStatus.api_error, f"claude exited {result.returncode}: {detail}")
    if not isinstance(envelope, dict):
        return failed_review(config, ReviewStatus.api_error, "claude output is not a JSON object")
    usage = _usage(envelope)
    subtype = envelope.get("subtype")
    if subtype == "error_max_structured_output_retries":
        return failed_review(config, ReviewStatus.schema_error, f"claude: {subtype}", usage)
    if subtype != "success" or envelope.get("is_error"):
        detail = envelope.get("result") or subtype or f"exit {result.returncode}"
        return failed_review(config, ReviewStatus.api_error, f"claude: {detail}", usage)
    if envelope.get("structured_output") is None:
        return failed_review(config, ReviewStatus.schema_error, "claude: success without structured_output", usage)
    return review_from_output(envelope["structured_output"], diff_text, config, usage)


def claude_cli_review(
    diff_text: str,
    repo: Path | None,
    config: ReviewerConfig,
    runner: Runner = run_subprocess,
    timeout_s: float = TIMEOUT_S,
) -> Review:
    """Review one diff with headless Claude Code running the aireview-code-review skill."""
    config = resolve_config(config)
    executable = shutil.which("claude") if runner is run_subprocess else "claude"
    if executable is None:
        return failed_review(config, ReviewStatus.api_error, "the `claude` CLI is not on PATH")
    prompt = f"{_skill_text(config)}\n\n---\n\n{build_user_message(diff_text, repo)}"
    try:
        result = runner(build_argv(config, executable), prompt, timeout_s)
    except subprocess.TimeoutExpired:
        return failed_review(config, ReviewStatus.api_error, f"timeout: claude ran longer than {timeout_s}s")
    except OSError as exc:
        return failed_review(config, ReviewStatus.api_error, f"cannot run claude: {exc}")
    return parse_envelope(result, diff_text, config)
