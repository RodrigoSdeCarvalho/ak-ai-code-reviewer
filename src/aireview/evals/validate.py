"""Dataset validator: schema, regenerated diff, label placement, leakage, test behaviour, duplicates."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aireview.diffs import IGNORED_DIRS, diff_dirs, parse_unified_diff
from aireview.evals.dataset import (
    CASE_FILE,
    MANIFEST_FILE,
    case_dirs,
    dataset_hash,
    load_case,
    load_yaml,
    resolve_root,
    update_case_yaml,
    write_manifest,
)
from aireview.evals.schema import Bug, Case, CaseKind

TEST_TIMEOUT_S = 60
FIX_TOLERANCE = 3  # a labelled range must lie within this many lines of a line the fix changes
GATED_SLICES = {
    "logic": {"logic"},
    "error_handling": {"error_handling"},
    "security": {"security"},
    "state": {"resource", "concurrency"},
}
MIN_SEEDED_PER_GATED_SLICE = 4

LEAKAGE_PATTERNS = [  # a letter may not precede the word, so `debug` passes but `bug_count` does not
    r"(?<![a-z])bug",
    r"(?<![a-z])fixme",
    r"(?<![a-z])seeded",
    r"todo:\s*fix",
    r"vulnerab",
    r"(?<![a-z])inject",
    r"off[- _]by[- _]one",
    r"race[- _]condition",
    r"(?<![a-z])leak",
]
_LEAKAGE_RE = re.compile("|".join(LEAKAGE_PATTERNS), re.IGNORECASE)
EXPECTED_GROUND_TRUTH = {CaseKind.seeded: {"test-validated"}, CaseKind.clean: {"none"}}


def size_bucket(diff_text: str) -> str:
    """S < 30 changed ('+'/'-') lines, M 30-120, L > 120."""
    n = sum(1 for line in diff_text.splitlines() if line[:1] in "+-" and not line.startswith(("+++ ", "--- ")))
    return "S" if n < 30 else "M" if n <= 120 else "L"


def _run_tests(case_dir: Path, with_fix: bool) -> tuple[int, str]:
    """Pytest exit code (-1 on timeout) and output for the case tests on after/ (+ fixed/ overlay)."""
    with tempfile.TemporaryDirectory(prefix="aireview-case-", ignore_cleanup_errors=True) as tmp:
        repo, tests = Path(tmp) / "repo", Path(tmp) / "case_tests"
        ignore = shutil.ignore_patterns(*IGNORED_DIRS, "*.pyc")
        shutil.copytree(case_dir / "after", repo, ignore=ignore)
        if with_fix:
            shutil.copytree(case_dir / "fixed", repo, ignore=ignore, dirs_exist_ok=True)
        shutil.copytree(case_dir / "tests", tests, ignore=ignore)
        ini = Path(tmp) / "pytest.ini"
        ini.write_text("[pytest]\n", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", str(ini), str(tests)]
        try:
            proc = subprocess.run(
                cmd, cwd=repo, env=env, capture_output=True, text=True, encoding="utf-8", timeout=TEST_TIMEOUT_S
            )
        except subprocess.TimeoutExpired:
            return -1, f"timeout after {TEST_TIMEOUT_S}s"
        return proc.returncode, (proc.stdout + proc.stderr)[-4000:]


def run_case_tests(case_dir: Path, with_fix: bool) -> tuple[bool, str]:
    """Run the case tests in a temp copy of after/ (optionally with fixed/ overlaid). True = all passed."""
    code, output = _run_tests(case_dir, with_fix)
    return code == 0, output


def _tree_files(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not any(part in IGNORED_DIRS for part in p.relative_to(root).parts) and p.suffix != ".pyc"
    }


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for rel, data in _tree_files(root).items():
        digest.update(rel.encode("utf-8") + b"\0" + data.replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def _fix_touched_lines(after: str, fixed: str) -> set[int]:
    """after/-side line numbers that the fix replaces or deletes, plus the neighbours of pure insertions."""
    a, b = after.splitlines(), fixed.splitlines()
    out: set[int] = set()
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            out.update(range(i1 + 1, i2 + 1))
        elif tag == "insert":
            out.update({i1, i1 + 1})
    return out


def _check_bugs(case: Case, case_dir: Path, diff_text: str) -> list[str]:
    problems: list[str] = []
    after, fixed_dir = case_dir / "after", case_dir / "fixed"
    changed = {fd.path: fd.changed_lines for fd in parse_unified_diff(diff_text)}
    for bug_id, n in Counter(b.id for b in case.bugs).items():
        if n > 1:
            problems.append(f"duplicate bug id {bug_id}")
    for bug in case.bugs:
        where = f"bug {bug.id} ({bug.file}:{bug.line_start}-{bug.line_end})"
        path = after / bug.file
        if not path.is_file():
            problems.append(f"{where}: file not found in after/")
            continue
        if bug.line_end < bug.line_start:
            problems.append(f"{where}: line_end < line_start")
            continue
        n_lines = len(path.read_text(encoding="utf-8").splitlines())
        if bug.line_end > n_lines:
            problems.append(f"{where}: beyond end of file ({n_lines} lines)")
            continue
        if case.kind in (CaseKind.seeded, CaseKind.real):
            span = set(range(bug.line_start, bug.line_end + 1))
            if not span & changed.get(bug.file, set()):
                problems.append(f"{where}: does not overlap a line changed by change.diff")
            fixed_file = fixed_dir / bug.file
            if fixed_file.is_file():
                touched = _fix_touched_lines(path.read_text(encoding="utf-8"), fixed_file.read_text(encoding="utf-8"))
                lo, hi = bug.line_start - FIX_TOLERANCE, bug.line_end + FIX_TOLERANCE
                if not any(lo <= t <= hi for t in touched):
                    problems.append(f"{where}: fixed/ changes nothing within {FIX_TOLERANCE} lines of the label")
            else:
                problems.append(f"{where}: fixed/ has no version of {bug.file}")
        problems += _check_alt_locations(case, bug, after, set(changed))
    return problems


def _check_alt_locations(case: Case, bug: Bug, after: Path, diff_files: set[str]) -> list[str]:
    """Each alternative location is a real range in after/. It need not overlap a changed line (the callee
    doing the work may be unchanged code), but for seeded/real it must be in a file the diff touches:
    findings on other files are out of scope, so an alternative there could never match."""
    problems: list[str] = []
    for loc in bug.alt_locations:
        where = f"bug {bug.id} alt location ({loc.file}:{loc.line_start}-{loc.line_end})"
        path = after / loc.file
        if not path.is_file():
            problems.append(f"{where}: file not found in after/")
            continue
        if loc.line_end < loc.line_start:
            problems.append(f"{where}: line_end < line_start")
            continue
        n_lines = len(path.read_text(encoding="utf-8").splitlines())
        if loc.line_end > n_lines:
            problems.append(f"{where}: beyond end of file ({n_lines} lines)")
            continue
        if case.kind in (CaseKind.seeded, CaseKind.real) and loc.file not in diff_files:
            problems.append(f"{where}: file is not part of change.diff, so no in-scope finding can point there")
        if (loc.file, loc.line_start, loc.line_end) == (bug.file, bug.line_start, bug.line_end):
            problems.append(f"{where}: repeats the labelled location")
    return problems


def _check_leakage(diff_text: str) -> list[str]:
    problems: list[str] = []
    for fd in parse_unified_diff(diff_text):
        if _LEAKAGE_RE.search(fd.path):
            problems.append(f"leakage: file name {fd.path} hints at the defect")
        for hunk in fd.hunks:
            for line in hunk.lines:
                if line.startswith("+") and (m := _LEAKAGE_RE.search(line)):
                    problems.append(
                        f"leakage: added line in {fd.path} contains {m.group(0)!r}: {line[1:].strip()[:80]}"
                    )
    return problems


def _check_fixed(case: Case, case_dir: Path) -> list[str]:
    fixed_dir, after = case_dir / "fixed", case_dir / "after"
    files = _tree_files(fixed_dir)
    if case.kind == CaseKind.clean:
        return ["clean case must not have fixed/"] if files else []
    if not files:
        return ["fixed/ is missing or empty"]
    problems: list[str] = []
    for rel, data in files.items():
        original = after / rel
        if not original.is_file():
            problems.append(f"fixed/{rel} has no counterpart in after/")
        elif original.read_bytes().replace(b"\r\n", b"\n") == data.replace(b"\r\n", b"\n"):
            problems.append(f"fixed/{rel} is identical to after/{rel}")
    return problems


def _check_tests(case: Case, case_dir: Path) -> list[str]:
    has_tests = (case_dir / "tests" / "test_case.py").is_file()
    if not has_tests:
        return [] if case.kind == CaseKind.real else ["tests/test_case.py is missing"]
    if case.kind == CaseKind.clean:
        code, out = _run_tests(case_dir, with_fix=False)
        return [] if code == 0 else [f"tests do not pass on after/ (exit {code}):\n{_indent(out)}"]
    problems: list[str] = []
    code, out = _run_tests(case_dir, with_fix=False)
    if code != 1:
        reason = "pass" if code == 0 else f"exit {code}; expected test failures (1), not errors/timeouts"
        problems.append(f"tests must fail on after/ ({reason}):\n{_indent(out)}")
    if (case_dir / "fixed").is_dir():
        code, out = _run_tests(case_dir, with_fix=True)
        if code != 0:
            problems.append(f"tests do not pass on after/ + fixed/ (exit {code}):\n{_indent(out)}")
    return problems


def _indent(text: str, keep: int = 25) -> str:
    return "\n".join("      " + line for line in text.strip().splitlines()[-keep:])


def validate_case(case_dir: Path, run_tests: bool = True, write: bool = False) -> list[str]:
    """Problems with one case (empty list = valid). `write` regenerates change.diff and size_bucket first."""
    try:
        case = load_case(case_dir)
    except Exception as exc:
        return [f"invalid {CASE_FILE}: {exc}"]
    problems: list[str] = []
    if case.id != case_dir.name:
        problems.append(f"id {case.id!r} differs from directory name {case_dir.name!r}")
    if not _tree_files(case_dir / "after"):
        return [*problems, "after/ is missing or empty"]

    fresh = diff_dirs(case_dir / "before", case_dir / "after")
    bucket = size_bucket(fresh)
    if write:
        (case_dir / "change.diff").write_text(fresh, encoding="utf-8", newline="\n")
        if case.size_bucket != bucket:
            update_case_yaml(case_dir, size_bucket=bucket)
            case = load_case(case_dir)
    if not fresh:
        problems.append("before/ and after/ are identical")
    diff_path = case_dir / "change.diff"
    if not diff_path.is_file():
        problems.append("change.diff is missing (run with --write)")
    elif diff_path.read_text(encoding="utf-8").replace("\r\n", "\n") != fresh:
        problems.append("change.diff is stale: it differs from a fresh before/ -> after/ diff (run with --write)")
    if case.size_bucket != bucket:
        problems.append(f"size_bucket is {case.size_bucket!r}, computed {bucket!r} (run with --write)")

    expected_gt = EXPECTED_GROUND_TRUTH.get(case.kind)
    if expected_gt and case.ground_truth not in expected_gt:
        problems.append(f"ground_truth {case.ground_truth!r} is not valid for kind {case.kind.value}")
    if case.kind == CaseKind.real and case.ground_truth not in {"fix-derived", "test-validated"}:
        problems.append(f"ground_truth {case.ground_truth!r} is not valid for kind real")
    if case.kind == CaseKind.clean and case.bugs:
        problems.append("clean case must not have bugs")
    if case.kind != CaseKind.clean and not case.bugs:
        problems.append(f"{case.kind.value} case must have at least one bug")

    problems += _check_bugs(case, case_dir, fresh)
    problems += _check_leakage(fresh)
    problems += _check_fixed(case, case_dir)
    if run_tests:
        problems += _check_tests(case, case_dir)
    return problems


def _duplicate_problems(dirs: list[Path]) -> dict[str, list[str]]:
    seen: dict[str, str] = {}
    out: dict[str, list[str]] = {}
    for case_dir in dirs:
        digest = tree_hash(case_dir / "after")
        if digest in seen:
            out.setdefault(case_dir.name, []).append(f"after/ is identical to case {seen[digest]}")
        else:
            seen[digest] = case_dir.name
    return out


def _summary(cases: list[Case]) -> list[str]:
    lines = ["", f"dataset: {len(cases)} cases"]

    def row(label: str, counter: Counter[str]) -> None:
        lines.append(f"  {label:<18} " + ", ".join(f"{k}={v}" for k, v in sorted(counter.items())))

    row("by kind", Counter(c.kind.value for c in cases))
    row("by split", Counter(c.split.value if c.split else "unassigned" for c in cases))
    row("by size", Counter(c.size_bucket or "?" for c in cases))
    row("by primary cat.", Counter(c.bugs[0].category.value for c in cases if c.bugs))
    bugs = [b for c in cases for b in c.bugs]
    row("bugs by severity", Counter(b.severity.value for b in bugs))
    row("bugs by category", Counter(b.category.value for b in bugs))
    seeded = [c for c in cases if c.kind == CaseKind.seeded]
    for name, cats in GATED_SLICES.items():
        n = sum(1 for c in seeded if c.bugs and c.bugs[0].category.value in cats)
        if n < MIN_SEEDED_PER_GATED_SLICE:
            lines.append(f"  warning: gated slice {name!r} has {n} seeded cases (< {MIN_SEEDED_PER_GATED_SLICE})")
    unassigned = sum(1 for c in cases if c.split is None)
    if unassigned:
        lines.append(f"  warning: {unassigned} cases have no split yet (run `aireview eval split`)")
    return lines


def _manifest_problem(root: Path, cases: list[Case]) -> str | None:
    path = root / MANIFEST_FILE
    if not path.is_file():
        return f"{MANIFEST_FILE} is missing (run `aireview eval split` or validate-dataset --write)"
    manifest = load_yaml(path) or {}
    listed = [(c.get("id"), c.get("split")) for c in manifest.get("cases") or []]
    actual = [(c.id, c.split.value if c.split else None) for c in sorted(cases, key=lambda c: c.id)]
    if manifest.get("dataset_hash") != dataset_hash(root) or listed != actual:
        return f"{MANIFEST_FILE} is stale (run validate-dataset --write or `aireview eval split`)"
    return None


def cli_validate(args: argparse.Namespace) -> int:
    root = resolve_root(args.dataset)
    dirs = case_dirs(root)
    if args.case:
        unknown = sorted(set(args.case) - {d.name for d in dirs})
        if unknown:
            print(f"unknown case ids: {', '.join(unknown)}", file=sys.stderr)
            return 1
        targets = [d for d in dirs if d.name in args.case]
    else:
        targets = dirs
    if not targets:
        print(f"no cases under {root / 'cases'}", file=sys.stderr)
        return 1

    workers = 1 if args.fast else min(8, os.cpu_count() or 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda d: validate_case(d, run_tests=not args.fast, write=args.write), targets))
    problems = {d.name: probs for d, probs in zip(targets, results, strict=True)}
    for name, dup in _duplicate_problems(dirs).items():
        if name in problems:
            problems[name] += dup

    cases: list[Case] = []
    for case_dir in dirs:
        try:
            cases.append(load_case(case_dir))
        except Exception:
            continue
    dataset_problems: list[str] = []
    if args.write and len(cases) == len(dirs):
        write_manifest(root)
    if not args.case and len(cases) == len(dirs) and (msg := _manifest_problem(root, cases)):
        dataset_problems.append(msg)

    by_id = {c.id: c for c in cases}
    print(f"{'case':<36} {'kind':<7} {'split':<6} {'size':<4} {'bugs':>4}  status")
    for case_dir in targets:
        c = by_id.get(case_dir.name)
        probs = problems[case_dir.name]
        status = "ok" if not probs else f"{len(probs)} problem(s)"
        kind = c.kind.value if c else "?"
        split = c.split.value if c and c.split else "-"
        size = (c.size_bucket or "?") if c else "?"
        bugs = len(c.bugs) if c else 0
        print(f"{case_dir.name:<36} {kind:<7} {split:<6} {size:<4} {bugs:>4}  {status}")
    for name, probs in problems.items():
        for p in probs:
            print(f"  {name}: {p}")
    for p in dataset_problems:
        print(f"  dataset: {p}")
    print("\n".join(_summary(cases)))

    n_bad = sum(1 for probs in problems.values() if probs) + len(dataset_problems)
    mode = "fast (tests skipped)" if args.fast else "full"
    print(f"\n{len(targets)} cases checked ({mode}); {'OK' if not n_bad else f'{n_bad} with problems'}")
    return 1 if n_bad else 0
