import json
import time
from pathlib import Path

import pytest

from aireview.evals.matching import MAX_JUDGE_TOL, location_candidates
from aireview.evals.metrics import METRIC_NAMES, compute_scores, metric_fn, paired_metric_delta
from aireview.evals.schema import Bug, BugTag, Case, Judgment, ReviewRow, Verdict
from aireview.models import Category, Finding, ReviewStatus, Severity, Usage

K = 3
FILE_LINES = 60


def make_case(case_id, kind="seeded", bugs=(), size="M", split="test"):
    return Case.model_validate(
        {
            "id": case_id,
            "kind": kind,
            "split": split,
            "size_bucket": size,
            "title": "t",
            "provenance": {"origin": "authored", "author": "a", "created": "2026-10-23"},
            "ground_truth": "none" if kind == "clean" else "test-validated",
            "bugs": list(bugs),
        }
    )


def make_bug(bug_id, line, severity="high", category="logic", must_find=True, file="app/m.py"):
    return Bug(
        id=bug_id,
        file=file,
        line_start=line,
        line_end=line + 1,
        severity=Severity(severity),
        category=Category(category),
        description="desc",
        must_find=must_find,
    )


def dataset():
    """8 seeded cases (one with two bugs, one with an optional bug) and 6 clean cases."""
    cases = []
    for i in range(8):
        bugs = [
            make_bug("b1", 10 + i, severity="high" if i % 2 == 0 else "medium", category=["logic", "security"][i % 2])
        ]
        if i == 0:
            bugs.append(make_bug("b2", 40, severity="critical", category="concurrency"))
        if i == 1:
            bugs.append(make_bug("opt", 50, severity="low", must_find=False))
        cases.append(make_case(f"seeded-{i}", bugs=bugs, size="S" if i < 4 else "M"))
    cases += [make_case(f"clean-{i}", kind="clean") for i in range(6)]
    return [(c, Path("unused") / c.id) for c in cases]


def finding_for(b: Bug, line=None, severity=None, category=None):
    return Finding(
        file=b.file,
        line=line or b.line_start,
        end_line=b.line_end if line is None else None,
        severity=severity or b.severity,
        category=category or b.category,
        title="t",
        description="d",
        confidence=0.9,
    )


def generic_finding(line, severity="medium"):
    return Finding(
        file="app/m.py",
        line=line,
        severity=Severity(severity),
        category=Category.maintainability,
        title="t",
        description="d",
        confidence=0.2,
    )


def rows_for(cases, make_findings, status=ReviewStatus.ok):
    return [
        ReviewRow(
            case_id=c.id,
            sample=s,
            status=status,
            findings=make_findings(c, s),
            usage=Usage(input_tokens=100, output_tokens=10, cost_usd=0.01, latency_ms=1000 + 100 * s),
        )
        for c, _ in cases
        for s in range(K)
    ]


def judge_all(cases, rows, verdict=Verdict.same):
    by_id = {c.id: c for c, _ in cases}
    return [
        Judgment(case_id=r.case_id, sample=r.sample, finding_index=i, bug_id=b, verdict=verdict)
        for r in rows
        for i, b in location_candidates(r.findings, by_id[r.case_id].bugs, MAX_JUDGE_TOL)
    ]


def oracle(case, sample):
    return [finding_for(b) for b in case.bugs if b.must_find]


def score(cases, rows, judgments=(), **kw):
    kw.setdefault("n_boot", 300)
    return compute_scores(cases, rows, list(judgments), **kw)


def value(scores, metric, mode="strict"):
    return scores["metrics"][mode][metric]["value"]


def test_oracle_scores_perfectly():
    cases = dataset()
    rows = rows_for(cases, oracle)
    s = score(cases, rows, judge_all(cases, rows))
    for mode in ("strict", "location"):
        for metric in ("recall", "recall_high", "precision", "f1", "pass_all_k", "pass_any_k"):
            assert value(s, metric, mode) == 1.0, (mode, metric)
        for metric in ("severity_exact", "severity_within1", "category_accuracy"):
            assert value(s, metric, mode) == 1.0
        assert value(s, "localization_mae", mode) == 0.0
        assert value(s, "fp_per_case", mode) == 0.0
        assert value(s, "clean_false_alarm_rate", mode) == 0.0
        assert value(s, "duplicate_rate", mode) == 0.0
    assert s["metrics"]["strict"]["recall"]["n"] == 9
    assert s["metrics"]["strict"]["recall_high"]["n"] == 5


def test_null_reviewer():
    cases = dataset()
    s = score(cases, rows_for(cases, lambda c, s: []))
    for mode in ("strict", "location"):
        assert value(s, "recall", mode) == 0.0
        assert value(s, "fp_per_case", mode) == 0.0
        assert value(s, "clean_false_alarm_rate", mode) == 0.0
        assert value(s, "precision", mode) is None  # undefined with no findings, never a fake 0 or 1
    assert s["metrics"]["strict"]["pass_any_k"]["value"] == 0.0


def test_spam_reviewer():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [generic_finding(n) for n in range(1, FILE_LINES + 1)])
    s = score(cases, rows)  # no judgments at all
    assert value(s, "recall", "location") == 1.0
    assert value(s, "precision", "location") < 0.05
    assert value(s, "clean_false_alarm_rate", "location") == 0.0  # spam is medium severity
    assert value(s, "recall", "strict") == 0.0
    assert s["metrics"]["strict"]["judge_missing"] > 0
    assert value(s, "duplicate_rate", "location") > 0.05


def test_high_severity_noise_raises_clean_false_alarm():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [generic_finding(5, "high")] if c.id == "clean-0" else [])
    s = score(cases, rows)
    assert value(s, "clean_false_alarm_rate") == pytest.approx(1 / 6)
    assert value(s, "clean_fp_per_case") == pytest.approx(1 / 6)
    assert value(s, "fp_per_case") == pytest.approx(1 / 14)


def test_duplicates_and_wrong_reason():
    cases = dataset()
    rows = rows_for(
        cases,
        lambda c, s: [finding_for(c.bugs[0]), finding_for(c.bugs[0], line=c.bugs[0].line_start + 2)] if c.bugs else [],
    )
    judgments = judge_all(cases, rows)
    s = score(cases, rows, judgments)
    assert value(s, "precision") == 1.0
    assert value(s, "duplicate_rate") == pytest.approx(0.5)
    # Same location, but the judge says the finding is about something else.
    s = score(cases, rows, judge_all(cases, rows, Verdict.different))
    assert value(s, "recall", "strict") == 0.0 and value(s, "precision", "strict") == 0.0
    assert value(s, "recall", "location") > 0.8


def test_judge_errors_count_as_unmatched_and_are_reported():
    cases = dataset()
    rows = rows_for(cases, oracle)
    judgments = judge_all(cases, rows)
    broken = judgments[0]
    judgments[0] = broken.model_copy(update={"verdict": None, "error": "api_error"})
    s = score(cases, rows, judgments)
    assert s["metrics"]["strict"]["judge_errors"] == 1
    assert value(s, "recall", "strict") < 1.0
    assert value(s, "recall", "location") == 1.0
    assert s["ops"]["judge_errors"] == 1


def test_infra_rows_are_excluded_and_counted():
    cases = dataset()
    rows = rows_for(cases, oracle)
    rows[0] = rows[0].model_copy(update={"status": ReviewStatus.api_error, "findings": []})
    rows = rows[:-1]  # last (case, sample) missing entirely
    s = score(cases, rows, judge_all(cases, rows))
    assert value(s, "recall") == 1.0
    assert s["status_counts"]["api_error"] == 1 and s["status_counts"]["missing"] == 1
    assert s["scorable_samples"] == 14 * K - 2 and s["total_samples"] == 14 * K
    per_case = {c["case_id"]: c for c in s["per_case"]}
    assert per_case[rows[0].case_id]["samples"][0]["strict"] is None


def test_optional_bug_is_neither_rewarded_nor_penalised():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [finding_for(b) for b in c.bugs])
    s = score(cases, rows, judge_all(cases, rows))
    assert value(s, "precision") == 1.0 and value(s, "recall") == 1.0
    per_bug = {(b["case_id"], b["bug_id"]): b for b in s["per_bug"]}
    assert per_bug[("seeded-1", "opt")]["strict"]["detect_rate"] == 1.0
    assert per_bug[("seeded-1", "opt")]["must_find"] is False


def test_per_bug_detect_rate_and_pass_k():
    cases = dataset()

    # seeded-0/b1 found only in sample 0; everything else always found.
    def flaky(case, sample):
        return [
            finding_for(b)
            for b in case.bugs
            if b.must_find and not (case.id == "seeded-0" and b.id == "b1" and sample > 0)
        ]

    rows = rows_for(cases, flaky)
    s = score(cases, rows, judge_all(cases, rows))
    per_bug = {(b["case_id"], b["bug_id"]): b for b in s["per_bug"]}
    assert per_bug[("seeded-0", "b1")]["strict"]["detected"] == [True, False, False]
    assert per_bug[("seeded-0", "b1")]["strict"]["detect_rate"] == pytest.approx(1 / 3)
    assert value(s, "pass_all_k") == pytest.approx(8 / 9)
    assert value(s, "pass_any_k") == 1.0
    assert value(s, "recall") == pytest.approx((9 + 8 + 8) / 27)


def test_tolerance_sensitivity():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [finding_for(b, line=b.line_end + 4) for b in c.bugs if b.must_find])
    s = score(cases, rows, judge_all(cases, rows))
    sens = s["tolerance_sensitivity"]
    assert sens["location"]["3"]["recall"] == 0.0 and sens["location"]["5"]["recall"] == 1.0
    assert sens["strict"]["0"]["recall"] == 0.0 and sens["strict"]["10"]["recall"] == 1.0
    assert value(s, "recall") == 0.0  # default tolerance 3


def test_severity_category_and_localization_on_tp_pairs():
    cases = dataset()
    rows = rows_for(
        cases,
        lambda c, s: [
            finding_for(b, line=b.line_start + 3, severity=Severity.low, category=Category.performance)
            for b in c.bugs
            if b.must_find
        ],
    )
    s = score(cases, rows, judge_all(cases, rows))
    assert value(s, "category_accuracy") == 0.0
    assert value(s, "localization_mae") == pytest.approx(2.0)  # 3 lines below line_start, 2 below line_end
    assert 0 <= value(s, "severity_within1") <= 1 and value(s, "severity_exact") < 1


def test_slices_and_insufficient_data():
    cases = dataset()
    rows = rows_for(cases, oracle)
    s = score(cases, rows, judge_all(cases, rows))
    sl = s["slices"]
    assert set(sl) >= {"kind", "size_bucket", "split", "category", "category_group", "severity"}
    assert sl["kind"]["clean"]["n_clean_cases"] == 6
    assert sl["kind"]["clean"]["strict"]["clean_false_alarm_rate"]["insufficient_data"] is False
    assert sl["kind"]["seeded"]["strict"]["recall"]["value"] == 1.0
    assert sl["category"]["security"]["n_bugs"] == 4
    assert sl["category"]["security"]["strict"]["recall"]["insufficient_data"] is True
    assert "state" in sl["category_group"]
    assert sl["severity"]["high"]["strict"]["recall"]["value"] == 1.0


def test_tag_and_seeded_size_slices():
    cases = dataset()
    tagged = cases[0][0].bugs[0].model_copy(update={"tags": [BugTag.unshown_context, BugTag.library_knowledge]})
    cases[0][0].bugs[0] = tagged
    cases[1][0].bugs[0] = cases[1][0].bugs[0].model_copy(update={"tags": [BugTag.unshown_context]})
    hits = {(cases[0][0].id, "b1")}  # the reviewer finds only the doubly tagged bug
    rows = rows_for(cases, lambda c, s: [finding_for(b) for b in c.bugs if (c.id, b.id) in hits])
    sl = score(cases, rows, judge_all(cases, rows))["slices"]
    assert set(sl["tag"]) == {"unshown_context", "library_knowledge", "untagged"}
    assert sl["tag"]["unshown_context"]["n_bugs"] == 2
    assert sl["tag"]["unshown_context"]["strict"]["recall"]["value"] == 0.5
    assert sl["tag"]["library_knowledge"]["strict"]["recall"]["value"] == 1.0
    assert sl["tag"]["untagged"]["n_bugs"] == 7  # 9 must-find bugs, 2 tagged; the optional bug is never sliced
    # sizes of seeded cases only: clean cases (all M here) do not dilute the M bucket
    assert sl["seeded_size_bucket"]["M"]["n_cases"] == 4
    assert sl["size_bucket"]["M"]["n_cases"] == 10
    assert sl["seeded_size_bucket"]["S"]["n_clean_cases"] == 0


def test_ci_contains_point_and_is_deterministic():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [finding_for(b) for b in c.bugs if b.must_find and (hash(c.id) + s) % 3])
    judgments = judge_all(cases, rows)
    a = score(cases, rows, judgments, seed=5)
    b = score(cases, rows, judgments, seed=5)
    assert a["metrics"] == b["metrics"]
    m = a["metrics"]["location"]["recall"]
    assert m["ci_low"] <= m["value"] <= m["ci_high"]


def test_grade_table_recomputes_headline():
    cases = dataset()
    rows = rows_for(cases, lambda c, s: [finding_for(b) for b in c.bugs[:1]] + [generic_finding(55)])
    s = json.loads(json.dumps(score(cases, rows, judge_all(cases, rows)), allow_nan=False))
    ids = [c.id for c, _ in cases]
    for metric in ("recall", "precision", "f1", "fp_per_case", "duplicate_rate"):
        for mode in ("strict", "location"):
            assert metric_fn(s, metric, mode)(ids) == pytest.approx(s["metrics"][mode][metric]["value"])
    assert {"strict", "location"} == {row["mode"] for row in s["grade_table"]}
    assert len(s["grade_table"]) == 2 * 14 * K
    assert set(METRIC_NAMES) <= set(s["metrics"]["strict"])


def test_paired_metric_delta():
    cases = dataset()
    good_rows = rows_for(cases, oracle)
    good = score(cases, good_rows, judge_all(cases, good_rows))
    bad = score(cases, rows_for(cases, lambda c, s: []))
    d = paired_metric_delta(good, bad, "recall", n_boot=300)
    assert d["delta"] == -1.0 and d["ci_high"] == -1.0 and d["n_cases"] == 14
    same = paired_metric_delta(good, good, "recall", n_boot=300)
    assert same["delta"] == 0.0 and same["half_width"] == 0.0


def test_ops():
    cases = dataset()
    rows = rows_for(cases, oracle)
    judgments = [j.model_copy(update={"usage": Usage(cost_usd=0.002)}) for j in judge_all(cases, rows)]
    ops = score(cases, rows, judgments)["ops"]
    assert ops["reviews"] == 14 * K
    assert ops["reviewer_cost_usd"] == pytest.approx(0.01 * 14 * K)
    assert ops["cost_usd_per_review"] == pytest.approx(0.01)
    assert ops["latency_p50_ms"] == 1100 and ops["latency_measured"] == 14 * K
    assert ops["judge_cost_usd"] == pytest.approx(0.002 * len(judgments))
    no_latency = [r.model_copy(update={"usage": Usage()}) for r in rows]
    assert score(cases, no_latency)["ops"]["latency_p95_ms"] is None


def test_full_bootstrap_is_fast():
    cases = dataset() * 4  # ~56 cases (ids repeat; fine for timing)
    cases = [(c.model_copy(update={"id": f"{c.id}-{i}"}), p) for i, (c, p) in enumerate(cases)]
    rows = rows_for(cases, oracle)
    start = time.perf_counter()
    compute_scores(cases, rows, judge_all(cases, rows), n_boot=10000)
    assert time.perf_counter() - start < 30


def test_f1_is_zero_not_undefined_for_a_sample_without_findings():
    """A sample that finds nothing has recall 0 and undefined precision: its f1 is 0 and it stays in the mean."""
    cases = dataset()
    rows = rows_for(cases, lambda c, s: oracle(c, s) if s < 2 else [])
    s = score(cases, rows, judge_all(cases, rows))
    assert value(s, "recall") == pytest.approx(2 / 3)
    assert value(s, "precision") == 1.0
    assert value(s, "f1") == pytest.approx(2 / 3)  # mean of [1, 1, 0], not nanmean -> 1.0
    assert s["metrics"]["strict"]["f1"]["ci_high"] < 1.0
    null = score(cases, rows_for(cases, lambda c, s: []))
    assert value(null, "f1") == 0.0 and value(null, "f1", "location") == 0.0
    assert s["tolerance_sensitivity"]["strict"]["3"]["f1"] == pytest.approx(2 / 3)


def test_truncated_and_refused_rows_are_counted_separately_and_never_scored():
    """Rows cut at max_tokens (truncated) or refused carry their own status; their findings never score."""
    cases = dataset()
    rows = rows_for(cases, oracle)
    spam = [generic_finding(n, severity="high") for n in range(1, FILE_LINES + 1)]
    rows[0] = rows[0].model_copy(update={"status": ReviewStatus.truncated, "findings": spam})
    rows[1] = rows[1].model_copy(update={"status": ReviewStatus.refused, "findings": spam})
    s = score(cases, rows, judge_all(cases, rows))
    assert s["status_counts"]["truncated"] == 1 and s["status_counts"]["refused"] == 1
    assert s["status_counts"]["api_error"] == 0
    assert s["scorable_samples"] == 14 * K - 2
    assert value(s, "precision") == 1.0 and value(s, "fp_per_case") == 0.0
    assert value(s, "recall") == 1.0


def test_precision_high_ignores_medium_nits_on_clean_cases():
    cases = dataset()

    def findings(case, sample):
        if case.kind.value == "clean":
            return [generic_finding(5, "medium")]
        return oracle(case, sample)

    s = score(cases, rows_for(cases, findings))
    assert value(s, "precision", "location") < 1.0
    assert value(s, "precision_high", "location") == 1.0
    assert value(s, "clean_false_alarm_rate", "location") == 0.0
