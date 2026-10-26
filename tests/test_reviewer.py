"""The API reviewer with a fake LLM client: request building, status mapping, scope, CLI, claude-cli backend."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from aireview.evals.schema import ReviewerConfig
from aireview.llm.base import LLMRequest, LLMResponse
from aireview.models import ReviewOutput, ReviewStatus, Usage
from aireview.reviewer import claude_cli, reviewer
from aireview.reviewer.claude_cli import RunResult, build_argv, claude_cli_review, parse_envelope
from aireview.reviewer.context import build_user_message
from aireview.reviewer.reviewer import (
    DEFAULT_CONFIG,
    build_request,
    load_prompt,
    parse_response,
    prompt_hash,
    review,
)
from aireview.settings import repo_root

DIFF = """diff --git a/app/cart.py b/app/cart.py
--- a/app/cart.py
+++ b/app/cart.py
@@ -1,2 +1,3 @@
 def total(items):
-    return sum(items)
+    s = sum(items)
+    return s * 2
"""
CONFIG = ReviewerConfig(
    name="v1-sonnet", backend="anthropic", model="claude-sonnet-5-5", prompt_version="v1", effort="medium"
)


def finding(file: str = "app/cart.py", line: int = 3) -> dict[str, Any]:
    return {
        "file": file,
        "line": line,
        "end_line": None,
        "severity": "high",
        "category": "logic",
        "title": "Total doubled",
        "description": "Every total is twice the real amount.",
        "suggestion": "Return s.",
        "confidence": 0.9,
    }


class FakeClient:
    def __init__(self, response: LLMResponse) -> None:
        self.response = response
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return self.response

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        return [self.complete(r) for r in requests]


def test_build_request() -> None:
    req = build_request(DIFF, None, CONFIG, sample=2)
    assert req.role == "reviewer"
    assert req.output_schema == ReviewOutput.model_json_schema()
    assert req.system == load_prompt("v1")
    assert req.prompt_version == "v1"
    assert (req.model, req.effort, req.max_tokens, req.sample) == ("claude-sonnet-5-5", "medium", 16000, 2)
    assert req.user == build_user_message(DIFF, None)
    assert req.key() == build_request(DIFF, None, CONFIG, sample=2).key()
    assert req.key() != build_request(DIFF, None, CONFIG, sample=1).key()


def test_prompt_loading() -> None:
    assert len(prompt_hash("v1")) == 64
    assert len(load_prompt("v1").splitlines()) < 120
    with pytest.raises(ValueError, match="unknown prompt version"):
        load_prompt("../settings")


def test_ok_review_scopes_and_normalises_paths() -> None:
    parsed = {"findings": [finding("b/app/cart.py"), finding("app/other.py")]}
    usage = Usage(input_tokens=10, output_tokens=5, cost_usd=0.01, latency_ms=100)
    client = FakeClient(LLMResponse(parsed=parsed, usage=usage, served_model="claude-sonnet-5-5"))
    result = review(DIFF, None, CONFIG, client)
    assert result.status == ReviewStatus.ok
    assert [f.file for f in result.findings] == ["app/cart.py"]
    assert [f.file for f in result.out_of_scope_findings] == ["app/other.py"]
    assert result.usage == usage
    assert (result.reviewer.model, result.reviewer.prompt_version, result.reviewer.backend) == (
        "claude-sonnet-5-5",
        "v1",
        "anthropic",
    )


def test_empty_findings_is_ok() -> None:
    result = parse_response(LLMResponse(raw_text='{"findings": []}'), DIFF, CONFIG)
    assert result.status == ReviewStatus.ok
    assert result.findings == []


@pytest.mark.parametrize(
    ("error_class", "status"),
    [
        ("truncated", ReviewStatus.truncated),
        ("refused", ReviewStatus.refused),
        ("schema_error", ReviewStatus.schema_error),
        ("api_error", ReviewStatus.api_error),
        ("timeout", ReviewStatus.api_error),
        ("model_mismatch", ReviewStatus.api_error),
        ("cassette_missing", ReviewStatus.api_error),
        (None, ReviewStatus.api_error),
    ],
)
def test_status_mapping(error_class: str | None, status: ReviewStatus) -> None:
    usage = Usage(input_tokens=3, cost_usd=0.002)
    response = LLMResponse(error="boom", error_class=error_class, usage=usage)
    result = parse_response(response, DIFF, CONFIG)
    assert result.status == status
    assert result.findings == []
    assert result.error == f"{error_class or 'api_error'}: boom"
    assert result.usage == usage


@pytest.mark.parametrize(
    "response",
    [
        LLMResponse(parsed={"findings": [{"file": "app/cart.py"}]}),
        LLMResponse(parsed={"issues": []}),
        LLMResponse(raw_text="not json"),
        LLMResponse(),
    ],
)
def test_invalid_output_is_schema_error(response: LLMResponse) -> None:
    assert parse_response(response, DIFF, CONFIG).status == ReviewStatus.schema_error


def test_default_config_matches_v1_sonnet_yaml() -> None:
    path = repo_root() / "evals" / "configs" / "v1-sonnet.yaml"
    assert reviewer.load_config(path) == DEFAULT_CONFIG


@pytest.mark.parametrize("name", ["v1-sonnet", "v1-haiku", "v1-opus", "static", "claude-cli-v1-sonnet"])
def test_configs_load(name: str) -> None:
    path = repo_root() / "evals" / "configs" / f"{name}.yaml"
    config = ReviewerConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    assert config.name == name


# ---------------------------------------------------------------- CLI


def _args(tmp_path: Path, **kw: Any) -> argparse.Namespace:
    diff_path = tmp_path / "change.diff"
    diff_path.write_text(DIFF, encoding="utf-8")
    base = dict(
        diff=str(diff_path),
        repo=None,
        base=None,
        out=str(tmp_path / "out" / "findings.json"),
        config=None,
        backend=None,
        model=None,
        prompt_version=None,
        effort=None,
    )
    return argparse.Namespace(**{**base, **kw})


def _use_fake(monkeypatch: pytest.MonkeyPatch, response: LLMResponse) -> FakeClient:
    client = FakeClient(response)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(reviewer, "_anthropic_client", lambda: client)
    return client


def test_cli_writes_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    client = _use_fake(monkeypatch, LLMResponse(parsed={"findings": [finding()]}))
    args = _args(tmp_path, effort="high", model="claude-haiku-5-5")
    assert reviewer.cli_review(args) == 0
    data = json.loads(Path(args.out).read_text(encoding="utf-8"))
    assert data["status"] == "ok"
    assert data["findings"][0]["line"] == 3
    assert data["reviewer"]["model"] == "claude-haiku-5-5"
    assert (client.requests[0].effort, client.requests[0].model) == ("high", "claude-haiku-5-5")
    assert "ok: 1 findings (1 high)" in capsys.readouterr().out


def test_cli_non_ok_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_fake(monkeypatch, LLMResponse(error="cut", error_class="truncated"))
    args = _args(tmp_path)
    assert reviewer.cli_review(args) == 2
    assert json.loads(Path(args.out).read_text(encoding="utf-8"))["status"] == "truncated"


def test_cli_usage_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert reviewer.cli_review(_args(tmp_path)) == 3
    assert reviewer.cli_review(_args(tmp_path, diff=None)) == 3
    assert reviewer.cli_review(_args(tmp_path, backend="static")) == 3
    assert reviewer.cli_review(_args(tmp_path, base="HEAD~1")) == 3


def test_cli_config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _use_fake(monkeypatch, LLMResponse(parsed={"findings": []}))
    config = tmp_path / "c.yaml"
    config.write_text("name: x\nbackend: anthropic\nmodel: claude-opus-5-5\nprompt_version: v1\n", encoding="utf-8")
    assert reviewer.cli_review(_args(tmp_path, config=str(config))) == 0
    assert client.requests[0].model == "claude-opus-5-5"
    assert client.requests[0].effort is None


# ---------------------------------------------------------------- claude-cli backend


def _envelope(**kw: Any) -> str:
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 1234,
        "total_cost_usd": 0.05,
        "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_input_tokens": 7},
        "structured_output": {"findings": [finding(), finding("elsewhere.py")]},
    }
    return json.dumps({**base, **kw})


def test_claude_cli_argv() -> None:
    argv = build_argv(CONFIG.model_copy(update={"backend": "claude-cli"}))
    assert argv[:5] == ["claude", "-p", "--bare", "--output-format", "json"]
    schema = argv[argv.index("--json-schema") + 1]
    assert json.loads(schema) == ReviewOutput.model_json_schema()
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5-5"
    assert "--max-turns" not in argv
    assert "--no-session-persistence" in argv
    assert argv[argv.index("--max-budget-usd") + 1] == "1"
    assert argv[-2:] == ["--tools", ""]


def test_claude_cli_review_with_fake_runner() -> None:
    calls: list[tuple[list[str], str]] = []

    def runner(argv: list[str], stdin: str, timeout_s: float) -> RunResult:
        calls.append((argv, stdin))
        return RunResult(0, _envelope(), "")

    config = CONFIG.model_copy(update={"backend": "claude-cli"})
    result = claude_cli_review(DIFF, None, config, runner=runner)
    assert result.status == ReviewStatus.ok
    assert len(result.findings) == 1 and len(result.out_of_scope_findings) == 1
    assert result.usage.cost_usd == 0.05
    assert result.usage.latency_ms == 1234
    assert result.usage.cache_read_input_tokens == 7
    assert result.reviewer.backend == "claude-cli"
    stdin = calls[0][1]
    assert stdin.startswith(load_prompt("v1").strip())
    assert stdin.endswith(build_user_message(DIFF, None))


@pytest.mark.parametrize(
    ("result", "status"),
    [
        (RunResult(0, _envelope(structured_output=None), ""), ReviewStatus.schema_error),
        (RunResult(0, _envelope(structured_output={"findings": [{}]}), ""), ReviewStatus.schema_error),
        (RunResult(1, _envelope(subtype="error_max_structured_output_retries"), ""), ReviewStatus.schema_error),
        (RunResult(1, _envelope(subtype="error_max_turns", is_error=True), ""), ReviewStatus.api_error),
        (RunResult(1, "", "Invalid API key"), ReviewStatus.api_error),
    ],
)
def test_claude_cli_envelope_failures(result: RunResult, status: ReviewStatus) -> None:
    assert parse_envelope(result, DIFF, CONFIG).status == status


def test_claude_cli_timeout() -> None:
    def runner(argv: list[str], stdin: str, timeout_s: float) -> RunResult:
        raise subprocess.TimeoutExpired(argv, timeout_s)

    result = claude_cli_review(DIFF, None, CONFIG, runner=runner, timeout_s=1)
    assert result.status == ReviewStatus.api_error
    assert result.error and result.error.startswith("timeout")


def test_cli_dispatches_claude_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[ReviewerConfig] = []

    def fake(diff_text: str, repo: Path | None, config: ReviewerConfig) -> Any:
        seen.append(config)
        return reviewer.Review(reviewer=reviewer.reviewer_info(config))

    monkeypatch.setattr(claude_cli, "claude_cli_review", fake)
    assert reviewer.cli_review(_args(tmp_path, backend="claude-cli")) == 0
    assert seen[0].backend == "claude-cli"
