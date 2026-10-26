"""The reviewer: one structured-output model call per diff, mapped to a `Review`.

Pure apart from the `LLMClient`: the same diff, repo and config always produce the same request.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from aireview import __version__
from aireview.diffs import changed_files, normalize_path, repo_diff
from aireview.evals.schema import ReviewerConfig
from aireview.llm.base import LLMClient, LLMRequest, LLMResponse
from aireview.models import Finding, Review, ReviewerInfo, ReviewOutput, ReviewStatus, Usage
from aireview.reviewer.context import build_user_message
from aireview.settings import DEFAULT_REVIEWER_MODEL

PROMPT_DIR = Path(__file__).parent / "prompts"
DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_CONFIG = ReviewerConfig(
    name="v1-sonnet",
    backend="anthropic",
    model=DEFAULT_REVIEWER_MODEL,
    prompt_version=DEFAULT_PROMPT_VERSION,
    effort="medium",
    max_tokens=16000,
)
EXIT_OK, EXIT_NOT_OK, EXIT_USAGE = 0, 2, 3

_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
# LLM error classes that are review statuses as they are; every other class (timeout, model_mismatch,
# cassette_missing, ...) is an api_error, with the original class kept in `Review.error`.
_STATUS_CLASSES = {
    "truncated": ReviewStatus.truncated,
    "refused": ReviewStatus.refused,
    "schema_error": ReviewStatus.schema_error,
}


@cache
def load_prompt(version: str) -> str:
    """System prompt text of `prompts/<version>.md`."""
    path = PROMPT_DIR / f"{version}.md"
    if not _VERSION_RE.fullmatch(version) or not path.is_file():
        known = sorted(p.stem for p in PROMPT_DIR.glob("*.md"))
        raise ValueError(f"unknown prompt version {version!r}; available: {known}")
    return path.read_text(encoding="utf-8")


def prompt_hash(version: str) -> str:
    """sha256 of the prompt text, recorded in run manifests."""
    return hashlib.sha256(load_prompt(version).encode("utf-8")).hexdigest()


def reviewer_info(config: ReviewerConfig) -> ReviewerInfo:
    return ReviewerInfo(
        version=__version__, prompt_version=config.prompt_version, model=config.model, backend=config.backend
    )


def failed_review(config: ReviewerConfig, status: ReviewStatus, error: str, usage: Usage | None = None) -> Review:
    """A review with no scorable output; `status` says why."""
    return Review(reviewer=reviewer_info(config), status=status, error=error, usage=usage or Usage())


def split_scope(findings: list[Finding], diff_text: str) -> tuple[list[Finding], list[Finding]]:
    """Normalise paths; return (findings on files in the diff, findings on other files)."""
    in_diff = changed_files(diff_text)
    in_scope: list[Finding] = []
    out_of_scope: list[Finding] = []
    for finding in findings:
        finding = finding.model_copy(update={"file": normalize_path(finding.file)})
        (in_scope if finding.file in in_diff else out_of_scope).append(finding)
    return in_scope, out_of_scope


def review_from_output(data: Any, diff_text: str, config: ReviewerConfig, usage: Usage) -> Review:
    """Validate a structured-output object against `ReviewOutput` and scope its findings to the diff."""
    try:
        output = ReviewOutput.model_validate(data)
    except ValidationError as exc:
        return failed_review(config, ReviewStatus.schema_error, f"output does not match ReviewOutput: {exc}", usage)
    findings, out_of_scope = split_scope(output.findings, diff_text)
    return Review(reviewer=reviewer_info(config), findings=findings, out_of_scope_findings=out_of_scope, usage=usage)


def resolve_config(config: ReviewerConfig) -> ReviewerConfig:
    """Fill a missing model or prompt version with the defaults."""
    return config.model_copy(
        update={
            "model": config.model or DEFAULT_REVIEWER_MODEL,
            "prompt_version": config.prompt_version or DEFAULT_PROMPT_VERSION,
        }
    )


def build_request(diff_text: str, repo: Path | None, config: ReviewerConfig, sample: int = 0) -> LLMRequest:
    """The reviewer call for one diff; deterministic, so its key addresses the cassette."""
    config = resolve_config(config)
    return LLMRequest(
        role="reviewer",
        model=config.model,
        system=load_prompt(config.prompt_version),
        user=build_user_message(diff_text, repo),
        output_schema=ReviewOutput.model_json_schema(),
        max_tokens=config.max_tokens,
        effort=config.effort,
        sample=sample,
        prompt_version=config.prompt_version,
    )


def parse_response(response: LLMResponse, diff_text: str, config: ReviewerConfig) -> Review:
    """Map an `LLMResponse` to a `Review`: serving failures get their own status, never empty findings."""
    config = resolve_config(config)
    if response.error is not None or response.error_class is not None:
        error_class = response.error_class or "api_error"
        status = _STATUS_CLASSES.get(error_class, ReviewStatus.api_error)
        return failed_review(config, status, f"{error_class}: {response.error}", response.usage)
    data: Any = response.parsed
    if data is None and response.raw_text:
        try:
            data = json.loads(response.raw_text)
        except json.JSONDecodeError as exc:
            return failed_review(config, ReviewStatus.schema_error, f"output is not valid JSON: {exc}", response.usage)
    if data is None:
        return failed_review(config, ReviewStatus.schema_error, "no output in the response", response.usage)
    return review_from_output(data, diff_text, config, response.usage)


def review(diff_text: str, repo: Path | None, config: ReviewerConfig, client: LLMClient, sample: int = 0) -> Review:
    """Review one diff with one model call."""
    request = build_request(diff_text, repo, config, sample)
    return parse_response(client.complete(request), diff_text, config)


# ---------------------------------------------------------------- CLI


def load_config(path: Path) -> ReviewerConfig:
    """A reviewer config YAML (`evals/configs/<name>.yaml`)."""
    return ReviewerConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _anthropic_client() -> LLMClient:
    from aireview.llm.anthropic_client import AnthropicClient

    return AnthropicClient()


def _run_backend(diff_text: str, repo: Path | None, config: ReviewerConfig) -> Review:
    if not diff_text.strip():
        return Review(reviewer=reviewer_info(config))
    if config.backend == "anthropic":
        return review(diff_text, repo, config, _anthropic_client())
    if config.backend == "claude-cli":
        from aireview.reviewer.claude_cli import claude_cli_review

        return claude_cli_review(diff_text, repo, config)
    if config.backend == "static":
        from aireview.reviewer.static_baseline import static_review

        if repo is None:
            raise ValueError("the static backend needs a repository")
        return static_review(diff_text, repo)
    raise ValueError(f"backend {config.backend!r} cannot run from `aireview review`")


def _usage_error(message: str) -> int:
    print(f"aireview review: {message}", file=sys.stderr)
    return EXIT_USAGE


def _summary(result: Review, out: Path, seconds: float) -> str:
    counts = Counter(f.severity.value for f in result.findings)
    by_sev = ", ".join(f"{counts[s]} {s}" for s in ("critical", "high", "medium", "low") if counts[s])
    parts = [f"{result.status.value}: {len(result.findings)} findings" + (f" ({by_sev})" if by_sev else "")]
    if result.out_of_scope_findings:
        parts.append(f"{len(result.out_of_scope_findings)} out of scope")
    parts.append(f"${result.usage.cost_usd:.4f}")
    parts.append(f"{seconds:.1f}s")
    if result.error:
        parts.append(f"error: {result.error}")
    return f"{' | '.join(parts)} -> {out}"


def cli_review(args: Any) -> int:
    """`aireview review`: exit 0 when the review is `ok`, 2 for any other status, 3 for bad arguments."""
    try:
        config = load_config(Path(args.config)) if args.config else DEFAULT_CONFIG
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return _usage_error(f"cannot load config {args.config}: {exc}")
    overrides = {
        "backend": args.backend,
        "model": args.model,
        "prompt_version": args.prompt_version,
        "effort": args.effort,
    }
    config = config.model_copy(update={k: v for k, v in overrides.items() if v is not None})
    if config.backend != "static":
        config = resolve_config(config)

    repo = Path(args.repo) if args.repo else None
    if repo is not None and not repo.is_dir():
        return _usage_error(f"--repo {repo} is not a directory")
    if args.base and repo is None:
        return _usage_error("--base needs --repo")
    if args.diff:
        diff_text = Path(args.diff).read_text(encoding="utf-8").replace("\r\n", "\n")
    elif repo is not None:
        diff_text = repo_diff(repo, args.base)
    else:
        return _usage_error("give --diff <file> or --repo <path> [--base <ref>]")
    if config.backend == "static" and repo is None:
        return _usage_error("the static backend needs --repo (it runs ruff and bandit on the files)")
    if config.backend == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        return _usage_error("the anthropic backend needs ANTHROPIC_API_KEY (set it in .env or the environment)")

    started = time.monotonic()
    result = _run_backend(diff_text, repo, config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(_summary(result, out, time.monotonic() - started))
    return EXIT_OK if result.status == ReviewStatus.ok else EXIT_NOT_OK
