"""Static baseline on a tiny repo: diagnostics restricted to changed lines, fixed rule mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from aireview.diffs import diff_dirs
from aireview.models import Category, ReviewStatus, Severity
from aireview.reviewer import static_baseline
from aireview.reviewer.static_baseline import ruff_rule, static_review

BEFORE = '''import subprocess


def run(cmd):
    """Run a fixed command."""
    return subprocess.call(["echo", cmd])


def old_unused():
    value = 1
    return 2
'''

AFTER = '''import subprocess


def run(cmd):
    """Run a fixed command."""
    return subprocess.call(["echo", cmd])


def old_unused():
    value = 1
    return 2


def search(term, items=[]):
    subprocess.call("grep " + term, shell=True)
    return undefined_helper(items)
'''


@pytest.fixture
def case(tmp_path: Path) -> tuple[str, Path]:
    before, after = tmp_path / "before" / "app", tmp_path / "after" / "app"
    before.mkdir(parents=True)
    after.mkdir(parents=True)
    (before / "tools.py").write_text(BEFORE, encoding="utf-8")
    (after / "tools.py").write_text(AFTER, encoding="utf-8")
    (after / "notes.txt").write_text("not python\n", encoding="utf-8")
    return diff_dirs(tmp_path / "before", tmp_path / "after"), tmp_path / "after"


def test_findings_only_on_changed_lines(case: tuple[str, Path]) -> None:
    diff, repo = case
    result = static_review(diff, repo)
    assert result.status == ReviewStatus.ok
    assert result.reviewer.backend == "static"
    assert result.findings, "expected diagnostics on the added function"
    assert {f.file for f in result.findings} == {"app/tools.py"}
    assert all(f.line >= 14 for f in result.findings)  # the unused `value` on line 10 is unchanged
    by_line = {(f.line, f.category) for f in result.findings}
    assert (14, Category.logic) in by_line  # B006 mutable default
    assert (15, Category.security) in by_line  # shell=True
    assert (16, Category.logic) in by_line  # F821 undefined name
    keys = [(f.file, f.line, f.category) for f in result.findings]
    assert len(keys) == len(set(keys))


def test_no_python_files_is_ok_and_empty(tmp_path: Path) -> None:
    (tmp_path / "before").mkdir()
    (tmp_path / "after").mkdir()
    (tmp_path / "after" / "README.md").write_text("hi\n", encoding="utf-8")
    result = static_review(diff_dirs(tmp_path / "before", tmp_path / "after"), tmp_path / "after")
    assert result.status == ReviewStatus.ok
    assert result.findings == []


def test_tool_failure_is_api_error(case: tuple[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(static_baseline, "RUFF_SELECT", "NOT-A-RULE")
    diff, repo = case
    result = static_review(diff, repo)
    assert result.status == ReviewStatus.api_error
    assert result.error and "ruff" in result.error


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("E999", (Category.logic, Severity.critical)),
        ("F821", (Category.logic, Severity.high)),
        ("F841", (Category.maintainability, Severity.low)),
        ("F632", (Category.logic, Severity.medium)),
        ("B006", (Category.logic, Severity.medium)),
        ("B904", (Category.error_handling, Severity.low)),
        ("S608", (Category.security, Severity.high)),
        ("S110", (Category.error_handling, Severity.medium)),
        ("S311", (Category.security, Severity.medium)),
        ("PLE0101", (Category.logic, Severity.medium)),
        ("PLR2004", (Category.maintainability, Severity.low)),
    ],
)
def test_rule_table(code: str, expected: tuple[Category, Severity]) -> None:
    assert ruff_rule(code) == expected
