"""Scores of a run: per-sample grade table, headline metrics with cluster-bootstrap CIs, slices, ops.

Pipeline: every (case, sample, mode) is graded into one flat row of integer counts (the grade table);
every headline metric is a per-sample pooled ratio of two grade columns, averaged over samples.
So the headline can be recomputed from `scores.json["grade_table"]` alone (see `metric_fn`).
Rows whose status is not `ok` are infra outcomes: counted in `status_counts`, excluded from quality metrics.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from aireview.evals.matching import MODES, location_candidates, match_sample
from aireview.evals.schema import Bug, Case, CaseKind, FindingOutcome, Judgment, ReviewRow, SampleOutcome, Verdict
from aireview.evals.stats import (
    CI_LEVEL,
    bootstrap_p_two_sided,
    case_weights,
    mean_over_samples,
    percentile_ci,
    pooled_ratio,
)
from aireview.models import SEVERITY_RANK, Finding, ReviewStatus, Severity

SCORES_SCHEMA_VERSION = "scores-1"
MIN_ITEMS = 6
HIGH_SEVERITIES = {Severity.critical, Severity.high}
CATEGORY_GROUPS = {"resource": "state", "concurrency": "state"}

GRADE_FIELDS = (
    "scorable",  # 1 if the review row has status ok
    "clean",  # 1 if scorable and the case is clean
    "n_findings",
    "tp",
    "fp",
    "dup",
    "tp_fp",
    "must_bugs",
    "detected_must",
    "high_bugs",  # must_find bugs with severity critical/high
    "detected_high",
    "alarm",  # clean case with >= 1 finding of severity >= high
    "clean_fp",
    "sev_exact",  # over tp pairs
    "sev_within1",
    "cat_correct",
    "loc_err_sum",  # sum of |finding.line - nearest labelled line| over tp pairs
    "judge_errors",  # strict: candidate pairs whose judgment failed (counted as not matched)
    "judge_missing",  # strict: candidate pairs with no judgment at all (counted as not matched)
    "tp_hi",  # tp findings the reviewer rated critical/high
    "tp_fp_hi",  # tp + fp findings the reviewer rated critical/high
)


@dataclass(frozen=True)
class RatioMetric:
    num: str
    den: str
    unit: str  # what `n` counts: bugs | high_bugs | cases | clean_cases | tp_pairs


RATIO_METRICS: dict[str, RatioMetric] = {
    "recall": RatioMetric("detected_must", "must_bugs", "bugs"),
    "recall_high": RatioMetric("detected_high", "high_bugs", "high_bugs"),
    "precision": RatioMetric("tp", "tp_fp", "cases"),
    "fp_per_case": RatioMetric("fp", "scorable", "cases"),
    "clean_false_alarm_rate": RatioMetric("alarm", "clean", "clean_cases"),
    "clean_fp_per_case": RatioMetric("clean_fp", "clean", "clean_cases"),
    "duplicate_rate": RatioMetric("dup", "n_findings", "cases"),
    "severity_exact": RatioMetric("sev_exact", "tp", "tp_pairs"),
    "severity_within1": RatioMetric("sev_within1", "tp", "tp_pairs"),
    "category_accuracy": RatioMetric("cat_correct", "tp", "tp_pairs"),
    "localization_mae": RatioMetric("loc_err_sum", "tp", "tp_pairs"),
    # Precision of the findings a reviewer would block a PR on: medium/low nits on otherwise correct code
    # (defensible review comments the dataset does not label) do not count against it.
    "precision_high": RatioMetric("tp_hi", "tp_fp_hi", "cases"),
}
METRIC_NAMES = ("recall", "recall_high", "precision", "f1", *list(RATIO_METRICS)[3:])

Verdicts = dict[tuple[int, str], Verdict | None]


# ---------------------------------------------------------------- grading


def verdict_index(judgments: Iterable[Judgment]) -> dict[tuple[str, int], Verdicts]:
    """(case_id, sample) -> {(finding_index, bug_id): verdict or None for a judge error}."""
    index: dict[tuple[str, int], Verdicts] = {}
    for j in judgments:
        index.setdefault((j.case_id, j.sample), {})[(j.finding_index, j.bug_id)] = j.verdict
    return index


def line_error(finding: Finding, bug: Bug) -> int:
    """|finding.line - nearest labelled line| (0 inside the labelled range)."""
    return max(0, bug.line_start - finding.line, finding.line - bug.line_end)


def _empty_grade(case: Case, sample: int, mode: str, status: str) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "sample": sample,
        "mode": mode,
        "kind": case.kind.value,
        "status": status,
    } | dict.fromkeys(GRADE_FIELDS, 0)


def grade_sample(
    case: Case, sample: int, row: ReviewRow | None, verdicts: Verdicts, mode: str, tol: int
) -> tuple[dict[str, Any], SampleOutcome | None]:
    """One grade-table row (and the matching outcome) for a (case, sample, mode)."""
    status = row.status.value if row else "missing"
    grade = _empty_grade(case, sample, mode, status)
    if row is None or row.status != ReviewStatus.ok:
        return grade, None
    findings = row.findings
    outcome = match_sample(case.id, sample, findings, case.bugs, verdicts, mode, tol)
    bugs = {b.id: b for b in case.bugs}
    must = [b for b in case.bugs if b.must_find]
    high = [b.id for b in must if b.severity in HIGH_SEVERITIES]
    tp_pairs = [
        (f, bugs[bug_id])
        for f, o, bug_id in zip(findings, outcome.finding_outcomes, outcome.matched_bug_for_finding, strict=True)
        if o == FindingOutcome.tp and bug_id is not None
    ]
    counts = Counter(outcome.finding_outcomes)
    is_clean = case.kind == CaseKind.clean
    pairs = location_candidates(findings, case.bugs, tol) if mode == "strict" else []
    grade.update(
        scorable=1,
        clean=int(is_clean),
        n_findings=len(findings),
        tp=counts[FindingOutcome.tp],
        fp=counts[FindingOutcome.fp],
        dup=counts[FindingOutcome.duplicate],
        tp_fp=counts[FindingOutcome.tp] + counts[FindingOutcome.fp],
        must_bugs=len(must),
        detected_must=len(outcome.detected_bugs),
        high_bugs=len(high),
        detected_high=sum(1 for b in high if b in outcome.detected_bugs),
        alarm=int(is_clean and any(f.severity in HIGH_SEVERITIES for f in findings)),
        clean_fp=counts[FindingOutcome.fp] if is_clean else 0,
        sev_exact=sum(f.severity == b.severity for f, b in tp_pairs),
        sev_within1=sum(abs(SEVERITY_RANK[f.severity] - SEVERITY_RANK[b.severity]) <= 1 for f, b in tp_pairs),
        cat_correct=sum(f.category == b.category for f, b in tp_pairs),
        loc_err_sum=sum(line_error(f, b) for f, b in tp_pairs),
        judge_errors=sum(1 for p in pairs if p in verdicts and verdicts[p] is None),
        judge_missing=sum(1 for p in pairs if p not in verdicts),
        tp_hi=sum(
            1
            for f, o in zip(findings, outcome.finding_outcomes, strict=True)
            if o == FindingOutcome.tp and f.severity in HIGH_SEVERITIES
        ),
        tp_fp_hi=sum(
            1
            for f, o in zip(findings, outcome.finding_outcomes, strict=True)
            if o in (FindingOutcome.tp, FindingOutcome.fp) and f.severity in HIGH_SEVERITIES
        ),
    )
    return grade, outcome


def grade_run(
    cases: Sequence[Case],
    rows: dict[tuple[str, int], ReviewRow],
    verdicts: dict[tuple[str, int], Verdicts],
    mode: str,
    tol: int,
    k: int,
) -> tuple[list[dict[str, Any]], dict[tuple[str, int], SampleOutcome]]:
    """Grade table rows for every (case, sample) of one mode, plus the outcomes of scorable samples."""
    table, outcomes = [], {}
    for case in cases:
        for s in range(k):
            grade, outcome = grade_sample(case, s, rows.get((case.id, s)), verdicts.get((case.id, s), {}), mode, tol)
            table.append(grade)
            if outcome is not None:
                outcomes[(case.id, s)] = outcome
    return table, outcomes


# ---------------------------------------------------------------- matrices


@dataclass
class GradeMatrix:
    """Grade-table columns of one mode as (n_cases, k) arrays, rows in `case_ids` order."""

    case_ids: list[str]
    fields: dict[str, np.ndarray]

    @classmethod
    def from_table(cls, case_ids: Sequence[str], table: Iterable[dict[str, Any]], mode: str, k: int) -> GradeMatrix:
        index = {c: i for i, c in enumerate(case_ids)}
        fields = {name: np.zeros((len(index), k)) for name in GRADE_FIELDS}
        for row in table:
            if row["mode"] == mode and row["case_id"] in index and row["sample"] < k:
                for name in GRADE_FIELDS:
                    fields[name][index[row["case_id"]], row["sample"]] = row[name]
        return cls(list(case_ids), fields)


@dataclass
class BugMatrix:
    """Per-bug detection of one mode: (n_bugs, k), 1/0, NaN for an unscorable sample."""

    bugs: list[Bug]
    case_index: np.ndarray
    detected: np.ndarray

    @classmethod
    def build(cls, cases: Sequence[Case], outcomes: dict[tuple[str, int], SampleOutcome], k: int) -> BugMatrix:
        bugs, case_index, rows = [], [], []
        for ci, case in enumerate(cases):
            for bug in case.bugs:
                bugs.append(bug)
                case_index.append(ci)
                rows.append([_bug_detected(outcomes.get((case.id, s)), bug) for s in range(k)])
        detected = np.array(rows, dtype=float).reshape(len(bugs), k)
        return cls(bugs, np.array(case_index, dtype=int), detected)


def _bug_detected(outcome: SampleOutcome | None, bug: Bug) -> float:
    """1/0 whether the bug was claimed in a scorable sample, NaN otherwise.

    A bug named by any finding (tp or duplicate) is claimed: an unassigned finding can only have an
    allowed edge to a bug that the assignment already gave to another finding.
    """
    if outcome is None:
        return math.nan
    return float(bug.id in outcome.matched_bug_for_finding)


def f1_of(recall: np.ndarray, precision: np.ndarray) -> np.ndarray:
    """Element-wise F1: 0 when both are 0, and 0 when recall is 0 and precision is undefined (a sample
    with no tp/fp findings found nothing). NaN only when recall is undefined (no must_find bugs) or
    precision is undefined while recall is not 0 (cannot happen: a detected bug needs a tp finding)."""
    total = recall + precision
    with np.errstate(divide="ignore", invalid="ignore"):
        f1 = np.where(total == 0, 0.0, 2 * recall * precision / total)
    return np.where(np.isnan(precision) & (recall == 0), 0.0, f1)


def per_sample_metric(gm: GradeMatrix, metric: str, keep: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Per-sample pooled value of a metric over the `keep` case rows; (k,) or (n_boot, k) with weights."""
    if metric == "f1":
        return f1_of(per_sample_metric(gm, "recall", keep, weights), per_sample_metric(gm, "precision", keep, weights))
    spec = RATIO_METRICS[metric]
    return pooled_ratio(gm.fields[spec.num][keep], gm.fields[spec.den][keep], weights)


def bug_arrays(bm: BugMatrix, bug_mask: np.ndarray, n_cases: int, stat: str) -> tuple[np.ndarray, np.ndarray]:
    """(num, den) per case for a bug-level stat: `recall` -> (n_cases, k); `pass_all_k`/`pass_any_k` -> (n_cases, 1)."""
    d = bm.detected[bug_mask]
    scorable = ~np.isnan(d)
    if stat == "recall":
        values, counts = np.nan_to_num(d), scorable.astype(float)
    else:
        n_scorable, n_detected = scorable.sum(axis=1), np.nansum(d, axis=1)
        ok = n_scorable > 0
        hit = (n_detected == n_scorable) if stat == "pass_all_k" else (n_detected > 0)
        values, counts = (ok & hit).astype(float)[:, None], ok.astype(float)[:, None]
    num = np.zeros((n_cases, values.shape[1]))
    den = np.zeros((n_cases, values.shape[1]))
    np.add.at(num, bm.case_index[bug_mask], values)
    np.add.at(den, bm.case_index[bug_mask], counts)
    return num, den


# ---------------------------------------------------------------- summaries


def _num(x: float | None) -> float | None:
    return None if x is None or not math.isfinite(x) else float(x)


def summarize(point: float, boot: np.ndarray | None, n: int) -> dict[str, Any]:
    """{value, ci_low, ci_high, n, insufficient_data}; NaN becomes null."""
    lo, hi = percentile_ci(boot) if boot is not None else (math.nan, math.nan)
    return {"value": _num(point), "ci_low": _num(lo), "ci_high": _num(hi), "n": n, "insufficient_data": n < MIN_ITEMS}


def ratio_summary(num: np.ndarray, den: np.ndarray, weights: np.ndarray | None, n: int) -> dict[str, Any]:
    point = mean_over_samples(pooled_ratio(num, den))
    boot = None if weights is None else mean_over_samples(pooled_ratio(num, den, weights))
    return summarize(point, boot, n)


def grade_metric_summary(
    gm: GradeMatrix, metric: str, keep: np.ndarray, weights: np.ndarray | None, n: int
) -> dict[str, Any]:
    point = mean_over_samples(per_sample_metric(gm, metric, keep))
    boot = None if weights is None else mean_over_samples(per_sample_metric(gm, metric, keep, weights))
    return summarize(point, boot, n)


def _units(cases: Sequence[Case], keep: np.ndarray, gm: GradeMatrix) -> dict[str, int]:
    kept = [cases[i] for i in keep]
    must = [b for c in kept for b in c.bugs if b.must_find]
    return {
        "bugs": len(must),
        "high_bugs": sum(1 for b in must if b.severity in HIGH_SEVERITIES),
        "cases": len(kept),
        "clean_cases": sum(1 for c in kept if c.kind == CaseKind.clean),
        "tp_pairs": int(gm.fields["tp"][keep].sum()),
    }


def mode_metrics(
    cases: Sequence[Case], gm: GradeMatrix, bm: BugMatrix, keep: np.ndarray, weights: np.ndarray | None
) -> dict[str, Any]:
    """Every case-level metric of one mode over the `keep` case rows."""
    units = _units(cases, keep, gm)
    out: dict[str, Any] = {}
    for name in METRIC_NAMES:
        unit = "bugs" if name == "f1" else RATIO_METRICS[name].unit
        out[name] = grade_metric_summary(gm, name, keep, weights, units[unit])
    must_mask = np.isin(bm.case_index, keep) & np.array([b.must_find for b in bm.bugs], dtype=bool)
    for stat in ("pass_all_k", "pass_any_k"):
        num, den = bug_arrays(bm, must_mask, len(cases), stat)
        out[stat] = ratio_summary(num[keep], den[keep], weights, units["bugs"])
    out["judge_errors"] = int(gm.fields["judge_errors"][keep].sum())
    out["judge_missing"] = int(gm.fields["judge_missing"][keep].sum())
    return out


def bug_slice_metrics(
    n_cases: int, bm: BugMatrix, bug_mask: np.ndarray, n_boot: int, seed: int
) -> dict[str, dict[str, Any]]:
    """recall / pass_all_k / pass_any_k over the bugs in `bug_mask`, bootstrapped over their cases."""
    keep = np.unique(bm.case_index[bug_mask])
    weights = case_weights(len(keep), n_boot, seed)
    n = int(bug_mask.sum())
    out = {}
    for stat in ("recall", "pass_all_k", "pass_any_k"):
        num, den = bug_arrays(bm, bug_mask, n_cases, stat)
        out[stat] = ratio_summary(num[keep], den[keep], weights, n)
    return out


# ---------------------------------------------------------------- assembly


@dataclass
class _Graded:
    table: list[dict[str, Any]]
    outcomes: dict[tuple[str, int], SampleOutcome]
    gm: GradeMatrix
    bm: BugMatrix


def _grade_all(
    cases: Sequence[Case], rows: dict[tuple[str, int], ReviewRow], verdicts: dict, tol: int, k: int
) -> dict[str, _Graded]:
    ids = [c.id for c in cases]
    graded = {}
    for mode in MODES:
        table, outcomes = grade_run(cases, rows, verdicts, mode, tol, k)
        graded[mode] = _Graded(
            table, outcomes, GradeMatrix.from_table(ids, table, mode, k), BugMatrix.build(cases, outcomes, k)
        )
    return graded


def _case_slices(
    cases: Sequence[Case], graded: dict[str, _Graded], n_boot: int, seed: int
) -> dict[str, dict[str, Any]]:
    # Each key maps a case to the slice values it belongs to (none: not in this dimension).
    keys: dict[str, Callable[[Case], set[str]]] = {
        "kind": lambda c: {c.kind.value},
        "size_bucket": lambda c: {c.size_bucket or "unknown"},
        "seeded_size_bucket": lambda c: {c.size_bucket or "unknown"} if c.kind == CaseKind.seeded else set(),
        "split": lambda c: {c.split.value if c.split else "unassigned"},
    }
    slices: dict[str, dict[str, Any]] = {}
    for dim, key in keys.items():
        slices[dim] = {}
        for value in sorted(set().union(*(key(c) for c in cases))):
            keep = np.array([i for i, c in enumerate(cases) if value in key(c)], dtype=int)
            weights = case_weights(len(keep), n_boot, seed)
            units = _units(cases, keep, graded["strict"].gm)
            entry: dict[str, Any] = {
                "n_cases": units["cases"],
                "n_bugs": units["bugs"],
                "n_clean_cases": units["clean_cases"],
            }
            for mode, g in graded.items():
                entry[mode] = mode_metrics(cases, g.gm, g.bm, keep, weights)
            slices[dim][value] = entry
    return slices


def _bug_slices(cases: Sequence[Case], graded: dict[str, _Graded], n_boot: int, seed: int) -> dict[str, dict[str, Any]]:
    bugs = graded["strict"].bm.bugs
    must = np.array([b.must_find for b in bugs], dtype=bool)
    keys: dict[str, Callable[[Bug], set[str]]] = {
        "category": lambda b: {b.category.value},
        "category_group": lambda b: {CATEGORY_GROUPS.get(b.category.value, b.category.value)},
        "severity": lambda b: {b.severity.value},
        "tag": lambda b: {t.value for t in b.tags} or {"untagged"},
    }
    slices: dict[str, dict[str, Any]] = {}
    for dim, key in keys.items():
        slices[dim] = {}
        for value in sorted(set().union(*(key(b) for b, m in zip(bugs, must, strict=True) if m))):
            mask = must & np.array([value in key(b) for b in bugs], dtype=bool)
            entry: dict[str, Any] = {"n_bugs": int(mask.sum())}
            for mode, g in graded.items():
                entry[mode] = bug_slice_metrics(len(cases), g.bm, mask, n_boot, seed)
            slices[dim][value] = entry
    return slices


def _per_bug(cases: Sequence[Case], graded: dict[str, _Graded]) -> list[dict[str, Any]]:
    out = []
    index = 0
    for case in cases:
        for bug in case.bugs:
            entry = {"case_id": case.id, "bug_id": bug.id, "kind": case.kind.value} | bug.model_dump(
                mode="json", exclude={"id", "description"}
            )
            for mode, g in graded.items():
                row = g.bm.detected[index]
                flags = [None if np.isnan(v) else bool(v) for v in row]
                scored = [f for f in flags if f is not None]
                entry[mode] = {"detected": flags, "detect_rate": _num(sum(scored) / len(scored)) if scored else None}
            out.append(entry)
            index += 1
    return out


def _per_case(cases: Sequence[Case], rows: dict, graded: dict[str, _Graded], k: int) -> list[dict[str, Any]]:
    out = []
    for case in cases:
        samples = []
        for s in range(k):
            row = rows.get((case.id, s))
            sample: dict[str, Any] = {
                "sample": s,
                "status": row.status.value if row else "missing",
                "n_findings": len(row.findings) if row else 0,
            }
            for mode, g in graded.items():
                o = g.outcomes.get((case.id, s))
                sample[mode] = None if o is None else _outcome_dict(o)
            samples.append(sample)
        out.append(
            {
                "case_id": case.id,
                "kind": case.kind.value,
                "split": case.split.value if case.split else None,
                "size_bucket": case.size_bucket,
                "must_find_bugs": [b.id for b in case.bugs if b.must_find],
                "samples": samples,
            }
        )
    return out


def _outcome_dict(o: SampleOutcome) -> dict[str, Any]:
    counts = Counter(o.finding_outcomes)
    return {
        "tp": counts[FindingOutcome.tp],
        "fp": counts[FindingOutcome.fp],
        "dup": counts[FindingOutcome.duplicate],
        "detected": o.detected_bugs,
        "missed": o.missed_bugs,
        "finding_outcomes": [x.value for x in o.finding_outcomes],
        "matched_bug_for_finding": o.matched_bug_for_finding,
    }


def _tolerance_sensitivity(
    cases: Sequence[Case], rows: dict, verdicts: dict, tolerances: Sequence[int], k: int
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {mode: {} for mode in MODES}
    keep = np.arange(len(cases))
    for tol in tolerances:
        for mode, g in _grade_all(cases, rows, verdicts, tol, k).items():
            entry = {
                m: _num(mean_over_samples(per_sample_metric(g.gm, m, keep))) for m in ("recall", "precision", "f1")
            }
            if mode == "strict":
                entry["judge_errors"] = int(g.gm.fields["judge_errors"].sum())
                entry["judge_missing"] = int(g.gm.fields["judge_missing"].sum())
            out[mode][str(tol)] = entry
    return out


def ops_summary(rows: Sequence[ReviewRow], judgments: Sequence[Judgment]) -> dict[str, Any]:
    """Spend, latency and tokens of the reviewer, and the judge's spend reported separately."""
    latencies = [r.usage.latency_ms for r in rows if r.usage.latency_ms is not None]
    cost = sum(r.usage.cost_usd for r in rows)
    p50, p95 = np.percentile(latencies, [50, 95]) if latencies else (math.nan, math.nan)
    return {
        "reviews": len(rows),
        "reviewer_cost_usd": _num(cost),
        "cost_usd_per_review": _num(cost / len(rows)) if rows else None,
        "latency_measured": len(latencies),
        "latency_p50_ms": _num(p50),
        "latency_p95_ms": _num(p95),
        "input_tokens": sum(r.usage.input_tokens for r in rows),
        "output_tokens": sum(r.usage.output_tokens for r in rows),
        "cache_read_input_tokens": sum(r.usage.cache_read_input_tokens for r in rows),
        "cache_creation_input_tokens": sum(r.usage.cache_creation_input_tokens for r in rows),
        "judge_calls": len(judgments),
        "judge_cost_usd": _num(sum(j.usage.cost_usd for j in judgments)),
        "judge_errors": sum(1 for j in judgments if j.verdict is None),
    }


def compute_scores(
    cases: Sequence[tuple[Case, Path]],
    rows: Sequence[ReviewRow],
    judgments: Sequence[Judgment],
    tolerance: int = 3,
    tolerances: Sequence[int] = (0, 3, 5, 10),
    n_boot: int = 10000,
    seed: int = 0,
    samples: int | None = None,
) -> dict[str, Any]:
    """The `scores.json` content of a run (schema in design.md §10).

    `samples` is the k the run asked for; by default the highest sample index seen + 1. Rows of
    cases not in `cases` are ignored; a (case, sample) with no row counts as `missing`.
    """
    case_list = [c for c, _ in cases]
    ids = {c.id for c in case_list}
    run_rows = [r for r in rows if r.case_id in ids]
    k = samples if samples is not None else max((r.sample + 1 for r in run_rows), default=0)
    by_key = {(r.case_id, r.sample): r for r in run_rows if r.sample < k}
    verdicts = verdict_index(j for j in judgments if j.case_id in ids)
    graded = _grade_all(case_list, by_key, verdicts, tolerance, k)

    keep = np.arange(len(case_list))
    weights = case_weights(len(case_list), n_boot, seed)
    status_counts = Counter(r.status.value for r in by_key.values())
    status_counts_out = {s.value: status_counts.get(s.value, 0) for s in ReviewStatus}
    status_counts_out["missing"] = len(case_list) * k - len(by_key)
    must = [b for c in case_list for b in c.bugs if b.must_find]
    return {
        "schema_version": SCORES_SCHEMA_VERSION,
        "tolerance": tolerance,
        "tolerances": list(tolerances),
        "samples": k,
        "n_boot": n_boot,
        "seed": seed,
        "ci_level": CI_LEVEL,
        "min_items": MIN_ITEMS,
        "counts": {
            "cases": len(case_list),
            "cases_by_kind": dict(sorted(Counter(c.kind.value for c in case_list).items())),
            "must_find_bugs": len(must),
            "high_bugs": sum(1 for b in must if b.severity in HIGH_SEVERITIES),
        },
        "status_counts": status_counts_out,
        "total_samples": len(case_list) * k,
        "scorable_samples": status_counts.get(ReviewStatus.ok.value, 0),
        "out_of_scope_findings": sum(len(r.out_of_scope_findings) for r in by_key.values()),
        "metrics": {mode: mode_metrics(case_list, g.gm, g.bm, keep, weights) for mode, g in graded.items()},
        "slices": _case_slices(case_list, graded, n_boot, seed) | _bug_slices(case_list, graded, n_boot, seed),
        "per_bug": _per_bug(case_list, graded),
        "per_case": _per_case(case_list, by_key, graded, k),
        "grade_table": [row for g in graded.values() for row in g.table],
        "tolerance_sensitivity": _tolerance_sensitivity(case_list, by_key, verdicts, tolerances, k),
        "ops": ops_summary(list(by_key.values()), [j for j in judgments if j.case_id in ids]),
    }


# ---------------------------------------------------------------- comparisons from scores.json


def grade_matrix(scores: dict[str, Any], mode: str = "strict") -> GradeMatrix:
    """Rebuild the (n_cases, k) grade arrays of one mode from a scores.json dict."""
    case_ids = [c["case_id"] for c in scores["per_case"]]
    return GradeMatrix.from_table(case_ids, scores["grade_table"], mode, scores["samples"])


def metric_fn(scores: dict[str, Any], metric: str, mode: str = "strict") -> Callable[[list[str]], float]:
    """A stat function over (resampled) case-id lists, for `stats.cluster_bootstrap` / `paired_bootstrap_delta`."""
    gm = grade_matrix(scores, mode)
    index = {c: i for i, c in enumerate(gm.case_ids)}

    def stat(case_ids: list[str]) -> float:
        return float(
            mean_over_samples(per_sample_metric(gm, metric, np.array([index[c] for c in case_ids], dtype=int)))
        )

    return stat


def paired_metric_delta(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    metric: str,
    mode: str = "strict",
    n_boot: int = 10000,
    seed: int = 0,
) -> dict[str, Any]:
    """Vectorised paired cluster bootstrap of candidate - baseline over the cases both runs scored.

    Returns {delta, ci_low, ci_high, p_two_sided, half_width, n_cases}; half_width is the MDE proxy.
    """
    a, b = grade_matrix(baseline, mode), grade_matrix(candidate, mode)
    in_b = set(b.case_ids)
    common = [c for c in a.case_ids if c in in_b]
    keep_a = np.array([a.case_ids.index(c) for c in common], dtype=int)
    keep_b = np.array([b.case_ids.index(c) for c in common], dtype=int)
    point = mean_over_samples(per_sample_metric(b, metric, keep_b)) - mean_over_samples(
        per_sample_metric(a, metric, keep_a)
    )
    weights = case_weights(len(common), n_boot, seed)
    if weights is None:
        deltas = np.array([])
    else:
        deltas = mean_over_samples(per_sample_metric(b, metric, keep_b, weights)) - mean_over_samples(
            per_sample_metric(a, metric, keep_a, weights)
        )
    lo, hi = percentile_ci(deltas)
    return {
        "delta": _num(point),
        "ci_low": _num(lo),
        "ci_high": _num(hi),
        "p_two_sided": _num(bootstrap_p_two_sided(deltas)),
        "half_width": _num((hi - lo) / 2),
        "n_cases": len(common),
    }
