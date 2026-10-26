"""Non-LLM floor: ruff and bandit diagnostics on the changed lines, mapped to findings with a fixed table.

Rule mapping (first matching prefix wins, most specific first):

| ruff rule / prefix                         | category        | severity |
|--------------------------------------------|-----------------|----------|
| E9 (syntax / IO errors)                    | logic           | critical |
| F821, F822, F823 (undefined names)         | logic           | high     |
| F401, F841, F811 (unused / redefined)      | maintainability | low      |
| F (other pyflakes)                         | logic           | medium   |
| B904 (raise without from in except)        | error_handling  | low      |
| B (other bugbear)                          | logic           | medium   |
| S102, S301, S307, S506, S602, S605, S608   | security        | high     |
| S110, S112 (try-except-pass / continue)    | error_handling  | medium   |
| S (other bandit rules in ruff)             | security        | medium   |
| PLE (pylint errors)                        | logic           | medium   |
| PL (other pylint rules)                    | maintainability | low      |

bandit results: category `security` (B110/B112 -> `error_handling`), severity from bandit's own
HIGH/MEDIUM/LOW, confidence from bandit's confidence. ruff overlaps bandit (the S rules), so a
diagnostic on a (file, line, category) that already has a finding is dropped.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from aireview import __version__
from aireview.diffs import normalize_path, parse_unified_diff
from aireview.models import Category, Finding, Review, ReviewerInfo, ReviewStatus, Severity, Usage

RUFF_SELECT = "E9,F,B,S,PL"
RUFF_CONFIDENCE = 0.9
TIMEOUT_S = 120

RUFF_RULES: list[tuple[str, Category, Severity]] = [
    ("E9", Category.logic, Severity.critical),
    ("F821", Category.logic, Severity.high),
    ("F822", Category.logic, Severity.high),
    ("F823", Category.logic, Severity.high),
    ("F401", Category.maintainability, Severity.low),
    ("F841", Category.maintainability, Severity.low),
    ("F811", Category.maintainability, Severity.low),
    ("F", Category.logic, Severity.medium),
    ("B904", Category.error_handling, Severity.low),
    ("B", Category.logic, Severity.medium),
    *((code, Category.security, Severity.high) for code in ("S102", "S301", "S307", "S506", "S602", "S605", "S608")),
    ("S110", Category.error_handling, Severity.medium),
    ("S112", Category.error_handling, Severity.medium),
    ("S", Category.security, Severity.medium),
    ("PLE", Category.logic, Severity.medium),
    ("PL", Category.maintainability, Severity.low),
]
BANDIT_CATEGORY = {"B110": Category.error_handling, "B112": Category.error_handling}
BANDIT_SEVERITY = {"HIGH": Severity.high, "MEDIUM": Severity.medium, "LOW": Severity.low}
BANDIT_CONFIDENCE = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}


class ToolError(RuntimeError):
    """A static tool did not run or produced unreadable output."""


def ruff_rule(code: str) -> tuple[Category, Severity]:
    """(category, severity) of a ruff rule code from `RUFF_RULES`."""
    for prefix, category, severity in RUFF_RULES:
        if code.startswith(prefix):
            return category, severity
    return Category.maintainability, Severity.low


def _run_tool(args: list[str], repo: Path, ok_codes: set[int]) -> Any:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", *args],
            cwd=repo,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"{args[0]}: {exc}") from exc
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = None
    if proc.returncode not in ok_codes or data is None:
        raise ToolError(f"{args[0]} exited {proc.returncode}: {(proc.stderr or proc.stdout).strip()[-500:]}")
    return data


def _relative(filename: str, repo: Path) -> str:
    path = Path(filename)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            pass
    return normalize_path(filename)


def _ruff_findings(files: list[str], repo: Path) -> list[Finding]:
    args = ["ruff", "check", "--isolated", "--no-cache", "--select", RUFF_SELECT, "--output-format", "json"]
    data = _run_tool([*args, "--exit-zero", *files], repo, {0})
    findings = []
    for diag in data:
        code = diag.get("code") or "E999"
        category, severity = ruff_rule(code)
        fix = (diag.get("fix") or {}).get("message")
        findings.append(
            Finding(
                file=_relative(diag["filename"], repo),
                line=max(1, int(diag["location"]["row"])),
                end_line=max(1, int((diag.get("end_location") or diag["location"])["row"])),
                severity=severity,
                category=category,
                title=f"{code}: {diag['message']}",
                description=f"{diag['message']} (ruff {code})",
                suggestion=fix,
                confidence=RUFF_CONFIDENCE,
            )
        )
    return findings


def _bandit_findings(files: list[str], repo: Path) -> list[Finding]:
    data = _run_tool(["bandit", "-f", "json", "-q", *files], repo, {0, 1})
    findings = []
    for res in data.get("results", []):
        test_id = res.get("test_id", "")
        line_range = res.get("line_range") or [res["line_number"]]
        findings.append(
            Finding(
                file=_relative(res["filename"], repo),
                line=int(res["line_number"]),
                end_line=max(int(res["line_number"]), int(max(line_range))),
                severity=BANDIT_SEVERITY.get(res.get("issue_severity", ""), Severity.low),
                category=BANDIT_CATEGORY.get(test_id, Category.security),
                title=f"{test_id}: {res['issue_text']}",
                description=f"{res['issue_text']} (bandit {test_id} {res.get('test_name', '')})".strip(),
                confidence=BANDIT_CONFIDENCE.get(res.get("issue_confidence", ""), 0.3),
            )
        )
    return findings


def static_review(diff_text: str, repo: Path) -> Review:
    """Run ruff and bandit on the changed Python files; keep diagnostics on changed lines."""
    started = time.monotonic()
    info = ReviewerInfo(version=__version__, backend="static")
    changed = {
        fd.path: fd.changed_lines
        for fd in parse_unified_diff(diff_text)
        if not fd.is_deleted and fd.path.endswith(".py") and (repo / fd.path).is_file()
    }
    files = sorted(changed)
    if not files:
        return Review(reviewer=info, usage=Usage(latency_ms=int((time.monotonic() - started) * 1000)))
    try:
        diagnostics = _ruff_findings(files, repo) + _bandit_findings(files, repo)
    except ToolError as exc:
        return Review(reviewer=info, status=ReviewStatus.api_error, error=f"static tool failed: {exc}")
    findings: list[Finding] = []
    seen: set[tuple[str, int, Category]] = set()
    for finding in diagnostics:
        key = (finding.file, finding.line, finding.category)
        if finding.line in changed.get(finding.file, set()) and key not in seen:
            seen.add(key)
            findings.append(finding)
    findings.sort(key=lambda f: (f.file, f.line, f.title))
    latency_ms = int((time.monotonic() - started) * 1000)
    return Review(reviewer=info, findings=findings, usage=Usage(latency_ms=latency_ms))
