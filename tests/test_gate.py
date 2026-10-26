"""Gate decisions and exit codes on synthetic scores (pure `decide`) and through the CLI."""

import argparse
import json
import shutil
from pathlib import Path

import pytest

from aireview.evals.baselines import ExactMatchJudge
from aireview.evals.gate import Policy, cli_gate, cli_promote, decide, load_gate_config, scores_summary
from aireview.evals.judge import candidate_items
from aireview.evals.metrics import compute_scores
from aireview.evals.report import compare_runs, write_json
from aireview.evals.schema import Bug, Case, ReviewRow
from aireview.models import Category, Finding, ReviewStatus, Severity

K = 3
GATE_DIR = Path(__file__).resolve().parents[1] / "evals" / "gate"


def make_cases() -> list[tuple[Case, Path]]:
    """8 seeded cases with one high bug each (logic/security alternating) and 6 clean cases."""
    out = []
    for i in range(8):
        bug = Bug(
            id="b1",
            file="app/m.py",
            line_start=10,
            line_end=10,
            severity=Severity.high,
            category=Category.logic if i % 2 == 0 else Category.security,
            description=f"defect {i}",
        )
        out.append(_case(f"seeded-{i}", "seeded", [bug]))
    out += [_case(f"clean-{i}", "clean", []) for i in range(6)]
    return out


def _case(case_id: str, kind: str, bugs: list[Bug]) -> tuple[Case, Path]:
    case = Case.model_validate(
        {
            "id": case_id,
            "kind": kind,
            "split": "test",
            "size_bucket": "S",
            "title": "t",
            "provenance": {"origin": "authored", "author": "a", "created": "2026-10-23"},
            "ground_truth": "none" if kind == "clean" else "test-validated",
            "bugs": [b.model_dump() for b in bugs],
        }
    )
    return case, Path("unused") / case_id


def _finding(description: str, severity: Severity = Severity.high) -> Finding:
    return Finding(
        file="app/m.py",
        line=10,
        severity=severity,
        category=Category.logic,
        title="t",
        description=description,
        confidence=0.9,
    )


def make_run(
    name: str,
    detected: int = 8,
    clean_alarms: bool = False,
    status: ReviewStatus = ReviewStatus.ok,
    errors: int = 0,
    **manifest_over,
):
    """(scores, manifest) of a synthetic run: the first `detected` seeded cases are found in every sample."""
    cases = make_cases()
    rows = []
    for idx, (case, _) in enumerate(cases):
        for s in range(K):
            findings = []
            if case.kind.value == "seeded" and idx < detected:
                findings = [_finding(case.bugs[0].description)]
            if case.kind.value == "clean" and clean_alarms:
                findings = [_finding("looks risky")]
            row_status = ReviewStatus.api_error if idx < errors and s == 0 else status
            rows.append(ReviewRow(case_id=case.id, sample=s, status=row_status, findings=findings))
    by_id = {c.id: c for c, _ in cases}
    items = [
        item
        for row in rows
        if row.status == ReviewStatus.ok
        for item in candidate_items(by_id[row.case_id], Path("unused"), row.sample, row.findings)
    ]
    judgments = ExactMatchJudge().judge_many(items)
    scores = compute_scores(cases, rows, judgments, n_boot=300, samples=K)
    manifest = {
        "run_id": name,
        "dataset_hash": "h1",
        "split": "test",
        "samples": K,
        "case_ids": [c.id for c, _ in cases],
        "judge_model": "exact-match",
        "judge_prompt_version": "exact-match-v1",
        "tolerance": 3,
        "extra": {},
    } | manifest_over
    return scores, manifest


def make_baseline(scores, manifest, run_dir: str | None = None) -> dict:
    return {
        "run_id": manifest["run_id"],
        "run_dir": run_dir,
        "manifest": manifest,
        "scores_summary": scores_summary(scores),
    }


@pytest.fixture(scope="module")
def config():
    return load_gate_config(GATE_DIR)


@pytest.fixture(scope="module")
def good():
    return make_run("good")


@pytest.fixture(scope="module")
def bad():
    return make_run("bad", detected=2)


def statuses(result) -> dict[str, str]:
    return {c.name: c.status for c in result.checks}


def test_pass_against_identical_baseline(config, good):
    scores, manifest = good
    compare = compare_runs(scores, scores, n_boot=300)
    result = decide(scores, manifest, make_baseline(scores, manifest), *config, compare=compare)
    assert (result.decision, result.exit_code) == ("PASS", 0)
    assert result.regression_basis == "paired"
    assert statuses(result)["regression.recall"] == "PASS"


def test_fail_on_paired_regression(config, good, bad):
    compare = compare_runs(good[0], bad[0], n_boot=300)
    result = decide(*bad, make_baseline(*good), *config, compare=compare)
    assert (result.decision, result.exit_code) == ("FAIL", 1)
    s = statuses(result)
    assert s["regression.recall"] == "FAIL"
    assert s["regression.kind:seeded.recall"] == "FAIL"
    assert s["newly_missed_critical"] == "FAIL"
    assert s["regression.category_group:logic.recall"] == "INSUFFICIENT_DATA"  # 4 bugs < 6: cannot fail


def test_unpaired_fallback_still_catches_regression(config, good, bad):
    result = decide(*bad, make_baseline(*good), *config, compare=None)
    assert result.decision == "FAIL"
    assert result.regression_basis == "unpaired-ci-overlap"
    check = next(c for c in result.checks if c.name == "regression.recall")
    assert check.status == "FAIL" and "fallback" in check.detail


def test_not_comparable(config, good):
    scores, manifest = good
    baseline = make_baseline(scores, manifest | {"dataset_hash": "other"})
    result = decide(scores, manifest, baseline, *config)
    assert (result.decision, result.exit_code) == ("NOT_COMPARABLE", 2)
    assert any("dataset_hash" in p for p in result.comparability_problems)


def test_nothing_gateable(config):
    scores, manifest = make_run("dead", status=ReviewStatus.api_error)
    result = decide(scores, manifest, None, *config)
    assert (result.decision, result.exit_code) == ("NOTHING_GATEABLE", 4)


def test_absolute_bars_advisory_while_pending_then_blocking(config):
    thresholds, tolerances, policy = config
    scores, manifest = make_run("noisy", clean_alarms=True)
    pending = decide(scores, manifest, None, thresholds, tolerances, policy)
    assert (pending.decision, pending.exit_code) == ("ADVISORY_ONLY", 0)
    assert statuses(pending)["absolute.clean_false_alarm_rate"] == "ADVISORY_FAIL"

    accepted = Policy.model_validate(
        policy.model_dump() | {"acceptance": {"state": "ACCEPTED", "by": "r", "date": "d"}}
    )
    result = decide(scores, manifest, None, thresholds, tolerances, accepted)
    assert (result.decision, result.exit_code) == ("FAIL", 1)


def test_completeness_blocks_on_api_errors_and_incomplete_runs(config):
    scores, manifest = make_run("flaky", errors=1)
    assert statuses(decide(scores, manifest, None, *config))["completeness.hard_errors"] == "FAIL"
    scores, manifest = make_run("stopped", extra={"incomplete": True})
    result = decide(scores, manifest, None, *config)
    assert result.decision == "FAIL" and statuses(result)["completeness.run_complete"] == "FAIL"


# ---------------------------------------------------------------- CLI


def _write_run(root: Path, scores, manifest) -> Path:
    run_dir = root / manifest["run_id"]
    run_dir.mkdir(parents=True)
    write_json(run_dir / "scores.json", scores)
    write_json(run_dir / "manifest.json", manifest)
    return run_dir


def test_cli_gate_and_promote(tmp_path: Path, good, bad):
    good_dir = _write_run(tmp_path / "runs", *good)
    bad_dir = _write_run(tmp_path / "runs", *bad)
    baseline = tmp_path / "baseline.json"

    def gate(run: Path) -> int:
        return cli_gate(argparse.Namespace(run=str(run), baseline=str(baseline), gate_dir=str(GATE_DIR)))

    def promote(run: Path, accept: bool = False) -> int:
        ns = argparse.Namespace(
            run=str(run), by="tester", reason="test", baseline=str(baseline), accept_regression=accept
        )
        return cli_promote(ns)

    assert gate(good_dir) == 0  # no baseline yet: regression skipped
    assert promote(good_dir) == 0
    record = json.loads(baseline.read_text(encoding="utf-8"))
    assert record["run_id"] == "good" and record["promoted_by"] == "tester" and record["run_dir"]

    assert gate(bad_dir) == 1
    gate_json = json.loads((bad_dir / "gate.json").read_text(encoding="utf-8"))
    assert gate_json["decision"] == "FAIL" and gate_json["regression_basis"] == "paired"
    assert (bad_dir / "gate.md").is_file()

    assert promote(bad_dir) == 1
    assert json.loads(baseline.read_text(encoding="utf-8"))["run_id"] == "good"
    assert promote(bad_dir, accept=True) == 0
    assert json.loads(baseline.read_text(encoding="utf-8"))["accepted_regression"] is True


def test_cli_gate_usage_errors(tmp_path: Path, good):
    run_dir = _write_run(tmp_path / "runs", *good)
    broken = tmp_path / "gate"
    shutil.copytree(GATE_DIR, broken)
    (broken / "policy.yaml").write_text("acceptance: {state: MAYBE}\n", encoding="utf-8")
    ns = argparse.Namespace(run=str(run_dir), baseline=str(tmp_path / "none.json"), gate_dir=str(broken))
    assert cli_gate(ns) == 3
    ns = argparse.Namespace(run=str(tmp_path / "missing"), baseline=str(tmp_path / "none.json"), gate_dir=str(GATE_DIR))
    assert cli_gate(ns) == 3


# ---------------------------------------------------------------- regressions


def test_blocking_failure_wins_over_not_comparable(config):
    """An incomplete, errored run against a relabelled baseline is FAIL (not promotable), not NOT_COMPARABLE."""
    good_scores, good_manifest = make_run("good")
    scores, manifest = make_run("broken", errors=3, extra={"incomplete": True})
    baseline = make_baseline(good_scores, good_manifest | {"dataset_hash": "h0"})
    result = decide(scores, manifest, baseline, *config)
    assert (result.decision, result.exit_code) == ("FAIL", 1)
    assert result.comparability_problems  # still reported
    s = statuses(result)
    assert s["completeness.run_complete"] == "FAIL" and s["completeness.hard_errors"] == "FAIL"


def test_different_k_is_not_comparable(config, good):
    """newly_missed (>= 2/3 vs 0/3) means nothing across k: a k=1 candidate is never gated against k=3."""
    scores, manifest = good
    result = decide(scores, manifest | {"samples": 1}, make_baseline(scores, manifest), *config)
    assert result.decision == "NOT_COMPARABLE"
    assert any(p.startswith("samples") for p in result.comparability_problems)


def _ns(run: Path, baseline: Path, accept: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        run=str(run),
        by="tester",
        reason="test",
        baseline=str(baseline),
        accept_regression=accept,
        gate_dir=str(GATE_DIR),
    )


def test_promote_regates_instead_of_trusting_a_stale_gate_json(tmp_path: Path, good, bad):
    good_dir = _write_run(tmp_path / "runs", *good)
    bad_dir = _write_run(tmp_path / "runs", *bad)
    baseline = tmp_path / "baseline.json"
    assert cli_gate(argparse.Namespace(run=str(bad_dir), baseline=str(baseline), gate_dir=str(GATE_DIR))) == 0
    assert json.loads((bad_dir / "gate.json").read_text(encoding="utf-8"))["decision"] != "FAIL"  # no baseline yet
    assert cli_promote(_ns(good_dir, baseline)) == 0
    assert cli_promote(_ns(bad_dir, baseline)) == 1  # regresses against the baseline promoted since
    assert json.loads(baseline.read_text(encoding="utf-8"))["run_id"] == "good"
    assert json.loads((bad_dir / "gate.json").read_text(encoding="utf-8"))["decision"] == "FAIL"


def test_promote_refuses_an_incomplete_run_that_is_not_comparable(tmp_path: Path, good):
    good_dir = _write_run(tmp_path / "runs", *good)
    broken = make_run("broken", errors=3, extra={"incomplete": True}, dataset_hash="h2")
    broken_dir = _write_run(tmp_path / "runs", *broken)
    baseline = tmp_path / "baseline.json"
    assert cli_promote(_ns(good_dir, baseline)) == 0
    assert cli_promote(_ns(broken_dir, baseline)) == 1
    assert json.loads(baseline.read_text(encoding="utf-8"))["run_id"] == "good"
    assert cli_promote(_ns(broken_dir, baseline, accept=True)) == 0
    record = json.loads(baseline.read_text(encoding="utf-8"))
    assert record["run_id"] == "broken" and record["accepted_regression"] is True


@pytest.mark.parametrize("change", ["manifest", "scores"])
def test_baseline_run_dir_changed_after_promotion_is_not_paired(tmp_path: Path, good, change):
    good_dir = _write_run(tmp_path / "runs", *good)
    baseline = tmp_path / "baseline.json"
    assert cli_promote(_ns(good_dir, baseline)) == 0
    if change == "manifest":  # `eval score <baseline dir> --tolerance 5` rewrites it in place
        write_json(good_dir / "manifest.json", good[1] | {"tolerance": 5})
    else:
        write_json(good_dir / "scores.json", make_run("good", detected=7)[0])
    candidate_dir = _write_run(tmp_path / "runs", *make_run("cand"))
    assert cli_gate(argparse.Namespace(run=str(candidate_dir), baseline=str(baseline), gate_dir=str(GATE_DIR))) == 0
    gate = json.loads((candidate_dir / "gate.json").read_text(encoding="utf-8"))
    assert gate["regression_basis"] == "unpaired-ci-overlap"
    assert gate["notes"] and "changed since promotion" in gate["notes"][0]
    assert "Notes:" in (candidate_dir / "gate.md").read_text(encoding="utf-8")
