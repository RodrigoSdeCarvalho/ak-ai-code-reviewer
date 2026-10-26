import argparse
import shutil
from pathlib import Path

import pytest
import yaml

from aireview.diffs import diff_dirs
from aireview.evals.dataset import load_yaml, update_case_yaml, write_manifest
from aireview.evals.validate import cli_validate, run_case_tests, size_bucket, validate_case
from aireview.settings import repo_root

BEFORE = 'def add(a, b):\n    """Sum."""\n    return a + b\n'
AFTER = BEFORE + '\n\ndef clamp(x, lo, hi):\n    """Limit x to [lo, hi]."""\n    return max(lo, min(x, lo))\n'
FIXED = AFTER.replace("min(x, lo)", "min(x, hi)")
TEST = "from calc.ops import add, clamp\n\n\ndef test_clamp():\n    assert add(1, 2) == 3\n    assert clamp(5, 0, 3) == 3\n"
BUG = {
    "id": "b1",
    "file": "calc/ops.py",
    "line_start": 8,
    "line_end": 8,
    "severity": "high",
    "category": "logic",
    "description": "clamps to lo instead of hi",
}


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _make_case(root: Path, case_id: str = "seeded-x-001", kind: str = "seeded", after: str = AFTER) -> Path:
    case = root / "cases" / case_id
    _write(case / "before" / "calc" / "__init__.py", "")
    _write(case / "before" / "calc" / "ops.py", BEFORE)
    _write(case / "after" / "calc" / "__init__.py", "")
    _write(case / "after" / "calc" / "ops.py", after)
    _write(case / "tests" / "test_case.py", TEST)
    if kind == "seeded":
        _write(case / "fixed" / "calc" / "ops.py", FIXED)
    data = {
        "id": case_id,
        "kind": kind,
        "title": "add clamp helper",
        "language": "python",
        "size_bucket": "S",
        "provenance": {"origin": "authored", "source": None, "author": "test", "created": "2026-10-23"},
        "ground_truth": "test-validated" if kind == "seeded" else "none",
        "bugs": [BUG] if kind == "seeded" else [],
    }
    _write(case / "case.yaml", yaml.safe_dump(data, sort_keys=False))
    _write(case / "change.diff", diff_dirs(case / "before", case / "after"))
    return case


def _clean_case(root: Path, case_id: str = "clean-x-001") -> Path:
    return _make_case(root, case_id, kind="clean", after=FIXED)


def _set_bug(case: Path, **fields) -> None:
    update_case_yaml(case, bugs=[{**BUG, **fields}])


def test_valid_seeded_and_clean_cases_pass(tmp_path):
    assert validate_case(_make_case(tmp_path)) == []
    assert validate_case(_clean_case(tmp_path)) == []


def test_run_case_tests_with_and_without_fix(tmp_path):
    case = _make_case(tmp_path)
    assert run_case_tests(case, with_fix=False)[0] is False
    passed, output = run_case_tests(case, with_fix=True)
    assert passed, output
    assert not list(case.rglob("__pycache__"))  # the case directory stays clean


def test_invalid_schema_and_id_mismatch(tmp_path):
    case = _make_case(tmp_path)
    update_case_yaml(case, kind="mystery")
    assert "invalid case.yaml" in validate_case(case, run_tests=False)[0]
    case2 = _make_case(tmp_path, "seeded-x-002")
    update_case_yaml(case2, id="other")
    assert any("differs from directory name" in p for p in validate_case(case2, run_tests=False))


def test_stale_diff_and_size_bucket_and_write_fixes_them(tmp_path):
    case = _make_case(tmp_path)
    _write(case / "change.diff", "stale\n")
    update_case_yaml(case, size_bucket="L")
    problems = validate_case(case, run_tests=False)
    assert any("change.diff is stale" in p for p in problems)
    assert any("size_bucket is 'L'" in p for p in problems)
    assert validate_case(case, run_tests=False, write=True) == []
    assert load_yaml(case / "case.yaml")["size_bucket"] == "S"


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"file": "calc/missing.py"}, "file not found in after/"),
        ({"line_start": 8, "line_end": 99}, "beyond end of file"),
        ({"line_start": 3, "line_end": 3}, "does not overlap a line changed"),
        ({"line_start": 8, "line_end": 7}, "line_end < line_start"),
    ],
)
def test_bug_label_problems(tmp_path, fields, message):
    case = _make_case(tmp_path)
    _set_bug(case, **fields)
    assert any(message in p for p in validate_case(case, run_tests=False))


def test_label_far_from_the_fix(tmp_path):
    long_after = AFTER + "".join(f"\n\nVALUE_{i} = {i}" for i in range(10)) + "\n"
    case = _make_case(tmp_path, after=long_after)
    _write(case / "fixed" / "calc" / "ops.py", long_after.replace("min(x, lo)", "min(x, hi)"))
    _write(case / "change.diff", diff_dirs(case / "before", case / "after"))
    _set_bug(case, line_start=25, line_end=25)
    assert any("fixed/ changes nothing within" in p for p in validate_case(case, run_tests=False))


def test_kind_rules(tmp_path):
    clean = _clean_case(tmp_path)
    update_case_yaml(clean, bugs=[BUG])
    _write(clean / "fixed" / "calc" / "ops.py", AFTER)
    problems = validate_case(clean, run_tests=False)
    assert "clean case must not have bugs" in problems
    assert "clean case must not have fixed/" in problems

    seeded = _make_case(tmp_path, "seeded-x-002")
    update_case_yaml(seeded, bugs=[], ground_truth="none")
    problems = validate_case(seeded, run_tests=False)
    assert "seeded case must have at least one bug" in problems
    assert any("ground_truth 'none' is not valid" in p for p in problems)


def test_leakage_in_added_lines_and_file_names(tmp_path):
    case = _make_case(tmp_path, after=AFTER.replace('"""Limit x to [lo, hi]."""', "# FIXME: off-by-one"))
    _write(case / "after" / "calc" / "bug_helpers.py", "VALUE = 1\n")
    validate_case(case, run_tests=False, write=True)
    problems = validate_case(case, run_tests=False)
    assert any("leakage: added line" in p and "FIXME" in p for p in problems)
    assert any("leakage: file name calc/bug_helpers.py" in p for p in problems)
    debug = _make_case(tmp_path, "seeded-x-002", after=AFTER.replace("Limit x", "Debug: limit x"))
    assert not any("leakage" in p for p in validate_case(debug, run_tests=False))


def test_fixed_overlay_problems(tmp_path):
    case = _make_case(tmp_path)
    _write(case / "fixed" / "calc" / "extra.py", "x = 1\n")
    _write(case / "fixed" / "calc" / "__init__.py", "")
    problems = validate_case(case, run_tests=False)
    assert "fixed/calc/extra.py has no counterpart in after/" in problems
    assert "fixed/calc/__init__.py is identical to after/calc/__init__.py" in problems
    shutil.rmtree(case / "fixed")
    assert "fixed/ is missing or empty" in validate_case(case, run_tests=False)


def test_seeded_tests_that_pass_on_after_are_rejected(tmp_path):
    case = _make_case(tmp_path)
    _write(case / "tests" / "test_case.py", "def test_ok():\n    assert True\n")
    assert any("tests must fail on after/ (pass)" in p for p in validate_case(case))


def test_seeded_tests_with_import_errors_are_rejected(tmp_path):
    case = _make_case(tmp_path)
    _write(case / "tests" / "test_case.py", "from calc.ops import missing\n\n\ndef test_x():\n    assert missing()\n")
    problems = validate_case(case)
    assert any("tests must fail on after/ (exit 2" in p for p in problems)
    assert any("tests do not pass on after/ + fixed/" in p for p in problems)


def test_clean_tests_must_pass(tmp_path):
    case = _clean_case(tmp_path)
    _write(case / "tests" / "test_case.py", "def test_no():\n    assert False\n")
    assert any("tests do not pass on after/" in p for p in validate_case(case))
    (case / "tests" / "test_case.py").unlink()
    assert "tests/test_case.py is missing" in validate_case(case)


def test_size_bucket_thresholds():
    def diff(n: int) -> str:
        return "--- a/x\n+++ b/x\n@@ -1 +1 @@\n" + "+x\n" * n

    assert [size_bucket(diff(n)) for n in (29, 30, 120, 121)] == ["S", "M", "M", "L"]


def _args(root: Path, **kw) -> argparse.Namespace:
    return argparse.Namespace(dataset=str(root), case=kw.get("case"), fast=kw.get("fast", True), write=kw.get("write"))


def test_cli_validate_duplicates_manifest_and_exit_codes(tmp_path, capsys):
    _make_case(tmp_path, "seeded-x-001")
    _clean_case(tmp_path, "clean-x-001")
    assert cli_validate(_args(tmp_path)) == 1  # no manifest yet
    assert "manifest.yaml is missing" in capsys.readouterr().out
    assert cli_validate(_args(tmp_path, write=True)) == 0
    out = capsys.readouterr().out
    assert "by kind            clean=1, seeded=1" in out
    assert "bugs by severity   high=1" in out

    _clean_case(tmp_path, "clean-x-002")
    write_manifest(tmp_path)
    assert cli_validate(_args(tmp_path)) == 1
    assert "after/ is identical to case clean-x-001" in capsys.readouterr().out
    assert cli_validate(_args(tmp_path, case=["nope"])) == 1


def test_template_cases_pass_full_validation():
    cases = repo_root() / "evals" / "dataset" / "cases"
    for case_id in ("seeded-template-01", "clean-template-01"):
        assert validate_case(cases / case_id) == [], case_id
