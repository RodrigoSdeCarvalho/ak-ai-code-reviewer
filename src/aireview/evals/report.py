"""Run artefact I/O, `report.md` rendering, and paired comparisons between two runs (`compare.json/.md`)."""

from __future__ import annotations

import argparse
import json
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

from aireview.evals.metrics import CATEGORY_GROUPS, paired_metric_delta
from aireview.evals.schema import Judgment, ReviewRow, RunManifest
from aireview.evals.stats import (
    bootstrap_p_two_sided,
    case_weights,
    mcnemar_exact,
    mean_over_samples,
    percentile_ci,
    pooled_ratio,
)

EXIT_OK, EXIT_NOT_COMPARABLE, EXIT_USAGE = 0, 2, 3
GATED_METRICS = ("recall", "recall_high", "precision", "clean_false_alarm_rate")
COMPARE_METRICS = ("recall", "recall_high", "precision", "precision_high", "f1", "clean_false_alarm_rate")
LOWER_IS_BETTER = {
    "clean_false_alarm_rate",
    "clean_fp_per_case",
    "fp_per_case",
    "duplicate_rate",
    "cost_usd_per_review",
}
COMPARE_KEYS = ("judge_model", "judge_prompt_version", "tolerance")
# k is a gate key: the newly-missed rule (baseline >= 2/3, candidate 0/3) and the per-sample means
# only mean the same thing at the same number of samples.
GATE_KEYS = ("dataset_hash", "split", "samples", *COMPARE_KEYS)
LISTING_LIMIT = 50
NO_CHANGE = "no detectable change"

# ---------------------------------------------------------------- run artefact I/O


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: Iterable[BaseModel | dict[str, Any]]) -> None:
    lines = [r.model_dump_json() if isinstance(r, BaseModel) else json.dumps(r, ensure_ascii=False) for r in rows]
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8", newline="\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_reviews(run_dir: Path) -> list[ReviewRow]:
    return [ReviewRow.model_validate(r) for r in read_jsonl(run_dir / "reviews.jsonl")]


def load_judgments(run_dir: Path) -> list[Judgment]:
    return [Judgment.model_validate(r) for r in read_jsonl(run_dir / "judgments.jsonl")]


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """(manifest, scores) of a run dir; raises FileNotFoundError naming the missing file."""
    for name in ("manifest.json", "scores.json"):
        if not (run_dir / name).is_file():
            raise FileNotFoundError(f"{run_dir / name} not found")
    return read_json(run_dir / "manifest.json"), read_json(run_dir / "scores.json")


# ---------------------------------------------------------------- formatting


def _f(x: float | None, digits: int = 3) -> str:
    return "n/a" if x is None or (isinstance(x, float) and not math.isfinite(x)) else f"{x:.{digits}f}"


def fmt_metric(m: dict[str, Any] | None, digits: int = 3) -> str:
    """`value [ci_low, ci_high]`, or n/a."""
    if not m or m.get("value") is None:
        return "n/a"
    ci = f" [{_f(m.get('ci_low'), digits)}, {_f(m.get('ci_high'), digits)}]" if m.get("ci_low") is not None else ""
    return f"{_f(m['value'], digits)}{ci}"


def _cell(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def md_table(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out


def _short(text: str | None, n: int = 12) -> str:
    return (text or "n/a")[:n]


# ---------------------------------------------------------------- report.md


def _header(scores: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    cfg = manifest.get("config", {})
    model = cfg.get("model") or "-"
    prompt = cfg.get("prompt_version") or "-"
    git = _short(manifest.get("git_sha"), 10) + (" (dirty)" if manifest.get("git_dirty") else "")
    mode = manifest.get("mode", "?") + (" (batch)" if manifest.get("batch") else "")
    counts = scores.get("counts", {})
    rows = [
        ("Config", f"{cfg.get('name')} (backend {cfg.get('backend')}, effort {cfg.get('effort') or '-'})"),
        ("Model / prompt", f"{model} / {prompt} (hash {_short(manifest.get('prompt_hash'))})"),
        ("Dataset", f"v{manifest.get('dataset_version')} (hash {_short(manifest.get('dataset_hash'))})"),
        ("Split / cases / k", f"{manifest.get('split')} / {counts.get('cases')} / {scores.get('samples')}"),
        ("Cases by kind", ", ".join(f"{k} {v}" for k, v in counts.get("cases_by_kind", {}).items())),
        ("Must-find bugs (high+)", f"{counts.get('must_find_bugs')} ({counts.get('high_bugs')})"),
        ("Mode", mode),
        ("Judge", f"{manifest.get('judge_model')} / {manifest.get('judge_prompt_version')}"),
        ("Location tolerance", f"±{scores.get('tolerance')} lines"),
        ("Created", f"{manifest.get('created_at')} (git {git})"),
        (
            "CIs",
            f"{int(scores.get('ci_level', 0.95) * 100)}% cluster bootstrap over cases, {scores.get('n_boot')} resamples",
        ),
    ]
    out = [f"# Eval run `{manifest.get('run_id')}`", "", *md_table(("", ""), rows), ""]
    if manifest.get("extra", {}).get("incomplete"):
        out += ["> **INCOMPLETE RUN**: the budget was exhausted mid-run; missing samples count as `missing`.", ""]
    return out


def _metric_rows(scores: dict[str, Any], names: Sequence[str], digits: int = 3) -> list[tuple[str, str, str, int]]:
    strict, location = scores["metrics"]["strict"], scores["metrics"]["location"]
    return [
        (name, fmt_metric(strict.get(name), digits), fmt_metric(location.get(name), digits), strict[name]["n"])
        for name in names
        if name in strict
    ]


def _headline(scores: dict[str, Any]) -> list[str]:
    header = ("metric", "strict (headline)", "location-only", "n")
    out = ["## Headline", ""]
    out += md_table(
        header, _metric_rows(scores, ("recall", "recall_high", "precision", "precision_high", "f1", "fp_per_case"))
    )
    strict = scores["metrics"]["strict"]
    out += [
        "",
        f"Strict = location candidate + judge `same`; location-only ignores the judge. Strict pairs with a judge error: "
        f"{strict.get('judge_errors', 0)}, without a judgment: {strict.get('judge_missing', 0)} (both count as not matched).",
        "",
        "## Clean cases (false alarms)",
        "",
        *md_table(header, _metric_rows(scores, ("clean_false_alarm_rate", "clean_fp_per_case"))),
        "",
        "`clean_false_alarm_rate` = share of clean cases with at least one finding of severity high or critical.",
        "",
        "## Consistency over k samples",
        "",
        *md_table(header, _metric_rows(scores, ("pass_all_k", "pass_any_k", "duplicate_rate"))),
        "",
        "pass^k = bug detected in every scorable sample; pass@k = in at least one.",
        "",
        "## Severity / category agreement (on true-positive pairs)",
        "",
        *md_table(header, _metric_rows(scores, ("severity_exact", "severity_within1", "category_accuracy"))),
        *md_table(("", "", "", ""), _metric_rows(scores, ("localization_mae",), digits=2))[2:],
        "",
    ]
    return out


def _slice_note(m: dict[str, Any] | None) -> str:
    return "INSUFFICIENT_DATA" if m and m.get("insufficient_data") else ""


def _slices(scores: dict[str, Any]) -> list[str]:
    slices = scores.get("slices", {})
    min_items = scores.get("min_items", 6)
    case_rows, bug_rows = [], []
    for dim in ("kind", "size_bucket", "seeded_size_bucket", "split"):
        for value, e in slices.get(dim, {}).items():
            s, loc = e["strict"], e["location"]
            note = _slice_note(s["recall"]) if e["n_bugs"] else ""
            case_rows.append(
                (
                    dim,
                    value,
                    e["n_cases"],
                    e["n_bugs"],
                    fmt_metric(s["recall"]),
                    fmt_metric(s["precision"]),
                    fmt_metric(s["clean_false_alarm_rate"]),
                    fmt_metric(loc["recall"]),
                    note,
                )
            )
    for dim in ("category_group", "category", "severity", "tag"):
        for value, e in slices.get(dim, {}).items():
            s, loc = e["strict"], e["location"]
            bug_rows.append(
                (
                    dim,
                    value,
                    e["n_bugs"],
                    fmt_metric(s["recall"]),
                    fmt_metric(s["pass_all_k"]),
                    fmt_metric(loc["recall"]),
                    _slice_note(s["recall"]),
                )
            )
    return [
        "## Slices",
        "",
        f"Slices with fewer than {min_items} units are marked INSUFFICIENT_DATA and cannot fail the gate.",
        "",
        *md_table(
            ("slice", "value", "cases", "bugs", "recall", "precision", "clean FA rate", "recall (loc)", "note"),
            case_rows,
        ),
        "",
        *md_table(("slice", "value", "bugs", "recall", "pass^k", "recall (loc)", "note"), bug_rows),
        "",
    ]


def _tolerance(scores: dict[str, Any]) -> list[str]:
    sens = scores.get("tolerance_sensitivity", {})
    strict, location = sens.get("strict", {}), sens.get("location", {})
    rows = [
        (
            f"±{tol}" + (" (scored)" if int(tol) == scores.get("tolerance") else ""),
            _f(strict[tol].get("recall")),
            _f(strict[tol].get("precision")),
            _f(strict[tol].get("f1")),
            _f(location.get(tol, {}).get("recall")),
            _f(location.get(tol, {}).get("precision")),
            f"{strict[tol].get('judge_errors', 0)} / {strict[tol].get('judge_missing', 0)}",
        )
        for tol in strict
    ]
    return [
        "## Location tolerance sensitivity (point values)",
        "",
        *md_table(
            ("tol", "recall", "precision", "f1", "recall (loc)", "precision (loc)", "judge err / missing"),
            rows,
        ),
        "",
    ]


def _status(scores: dict[str, Any]) -> list[str]:
    counts = scores.get("status_counts", {})
    total = scores.get("total_samples", 0)
    rows = [(k, v, _f(v / total if total else None)) for k, v in counts.items()]
    return [
        "## Serving outcomes",
        "",
        f"{scores.get('scorable_samples', 0)} of {total} samples scorable (status `ok`). "
        "Other statuses are infra outcomes, excluded from quality metrics, never scored as 'no findings'.",
        "",
        *md_table(("status", "samples", "share"), rows),
        "",
        f"Findings on files outside the diff (dropped, counted): {scores.get('out_of_scope_findings', 0)}.",
        "",
    ]


def _ops(scores: dict[str, Any]) -> list[str]:
    ops = scores.get("ops", {})
    if ops.get("latency_measured"):
        latency = f"p50 {_f(ops.get('latency_p50_ms'), 0)} ms, p95 {_f(ops.get('latency_p95_ms'), 0)} ms"
    else:
        latency = "not measured (batch, cached or synthetic)"
    rows = [
        ("reviews", ops.get("reviews")),
        ("reviewer cost (USD)", _f(ops.get("reviewer_cost_usd"), 4)),
        ("cost per review (USD)", _f(ops.get("cost_usd_per_review"), 4)),
        ("latency", f"{latency} over {ops.get('latency_measured', 0)} calls"),
        ("tokens in / out", f"{ops.get('input_tokens', 0)} / {ops.get('output_tokens', 0)}"),
        (
            "cache read / write",
            f"{ops.get('cache_read_input_tokens', 0)} / {ops.get('cache_creation_input_tokens', 0)}",
        ),
        ("judge calls / errors", f"{ops.get('judge_calls', 0)} / {ops.get('judge_errors', 0)}"),
        ("judge cost (USD)", _f(ops.get("judge_cost_usd"), 4)),
    ]
    return ["## Ops", "", *md_table(("", ""), rows), ""]


def _missed(scores: dict[str, Any]) -> list[str]:
    rows = []
    for bug in scores.get("per_bug", []):
        rate = bug["strict"]["detect_rate"]
        if not bug.get("must_find", True) or rate is None or rate >= 1:
            continue
        rows.append(
            (
                bug["case_id"],
                bug["bug_id"],
                f"{bug['file']}:{bug['line_start']}-{bug['line_end']}",
                bug["severity"],
                bug["category"],
                _f(rate, 2),
                _f(bug["location"]["detect_rate"], 2),
            )
        )
    rows.sort(key=lambda r: (float(r[5]), r[0], r[1]))
    return _listing(
        "Missed bugs (strict detect rate < 1)",
        ("case", "bug", "file:lines", "severity", "category", "detect (strict)", "detect (loc)"),
        rows,
    )


def _false_positives(
    scores: dict[str, Any], reviews: Sequence[ReviewRow] | None, triage: Sequence[dict[str, Any]] | None
) -> list[str]:
    if reviews is None:
        return ["## False positives (strict)", "", "(reviews.jsonl not available)", ""]
    by_key = {(r.case_id, r.sample): r for r in reviews}
    labels = {(t["case_id"], t["sample"], t["finding_index"]): t.get("label") for t in triage or []}
    rows = []
    for case in scores.get("per_case", []):
        for sample in case["samples"]:
            outcome, row = sample.get("strict"), by_key.get((case["case_id"], sample["sample"]))
            if outcome is None or row is None:
                continue
            for i, kind in enumerate(outcome["finding_outcomes"]):
                if kind != "fp" or i >= len(row.findings):
                    continue
                f = row.findings[i]
                label = labels.get((case["case_id"], sample["sample"], i))
                rows.append(
                    (
                        case["case_id"],
                        sample["sample"],
                        f"{f.file}:{f.line}",
                        f.severity.value,
                        f.title[:90],
                        label or "-",
                    )
                )
    return _listing(
        "False positives (strict)", ("case", "sample", "file:line", "severity", "title", "triage"), rows
    ) + _triage_summary(triage)


def _triage_summary(triage: Sequence[dict[str, Any]] | None) -> list[str]:
    if not triage:
        return []
    counts: dict[str, int] = {}
    for t in triage:
        key = t.get("label") or "judge_error"
        counts[key] = counts.get(key, 0) + 1
    return [
        "FP triage (advisory, never changes the headline): " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
        "",
    ]


def _listing(title: str, header: Sequence[str], rows: list[Sequence[Any]]) -> list[str]:
    out = [f"## {title}", ""]
    if not rows:
        return [*out, "None.", ""]
    out += md_table(header, rows[:LISTING_LIMIT])
    if len(rows) > LISTING_LIMIT:
        out.append(f"\n... {len(rows) - LISTING_LIMIT} more (see scores.json / reviews.jsonl).")
    return [*out, ""]


def render(
    scores: dict[str, Any],
    manifest: RunManifest | dict[str, Any],
    reviews: Sequence[ReviewRow] | None = None,
    triage: Sequence[dict[str, Any]] | None = None,
) -> str:
    """report.md for one run: header, headline, clean, consistency, slices, tolerance, status, ops, error analysis."""
    m = manifest.model_dump(mode="json") if isinstance(manifest, RunManifest) else manifest
    lines = [
        *_header(scores, m),
        *_headline(scores),
        *_slices(scores),
        *_tolerance(scores),
        *_status(scores),
        *_ops(scores),
        *_missed(scores),
        *_false_positives(scores, reviews, triage),
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_report(run_dir: Path) -> Path:
    manifest, scores = load_run(run_dir)
    reviews = load_reviews(run_dir) if (run_dir / "reviews.jsonl").exists() else None
    triage = read_jsonl(run_dir / "triage.jsonl") or None
    path = run_dir / "report.md"
    path.write_text(render(scores, manifest, reviews, triage), encoding="utf-8", newline="\n")
    return path


def cli_report(args: argparse.Namespace) -> int:
    try:
        path = write_report(Path(args.run_dir))
    except FileNotFoundError as exc:
        print(f"aireview eval report: {exc}")
        return EXIT_USAGE
    print(f"wrote {path}")
    return EXIT_OK


# ---------------------------------------------------------------- comparisons


def comparability_problems(
    baseline: dict[str, Any], candidate: dict[str, Any], keys: Sequence[str] = COMPARE_KEYS
) -> list[str]:
    """Why two run manifests cannot be compared (empty = comparable). Case sets must always match."""
    problems = [
        f"{key}: baseline {baseline.get(key)!r} != candidate {candidate.get(key)!r}"
        for key in keys
        if baseline.get(key) != candidate.get(key)
    ]
    a, b = set(baseline.get("case_ids", [])), set(candidate.get("case_ids", []))
    if a != b:
        problems.append(f"case sets differ: {len(a - b)} only in baseline, {len(b - a)} only in candidate")
    return problems


def _num(x: float) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def paired_ratio_delta(
    num_a: np.ndarray, den_a: np.ndarray, num_b: np.ndarray, den_b: np.ndarray, n_boot: int, seed: int
) -> dict[str, Any]:
    """Paired cluster bootstrap of pooled num/den (mean over samples), candidate (b) minus baseline (a).

    Arrays are (n_cases, k) in the same case order. Same draws as `metrics.paired_metric_delta`.
    """
    point = mean_over_samples(pooled_ratio(num_b, den_b)) - mean_over_samples(pooled_ratio(num_a, den_a))
    weights = case_weights(num_a.shape[0], n_boot, seed)
    deltas = (
        np.array([])
        if weights is None
        else mean_over_samples(pooled_ratio(num_b, den_b, weights))
        - mean_over_samples(pooled_ratio(num_a, den_a, weights))
    )
    lo, hi = percentile_ci(deltas)
    return {
        "delta": _num(point),
        "ci_low": _num(lo),
        "ci_high": _num(hi),
        "p_two_sided": _num(bootstrap_p_two_sided(deltas)),
        "half_width": _num((hi - lo) / 2),
        "n_cases": int(num_a.shape[0]),
    }


def restrict(scores: dict[str, Any], case_ids: Iterable[str]) -> dict[str, Any]:
    """A scores dict whose per_case / grade_table keep only `case_ids` (for paired slice deltas)."""
    keep = set(case_ids)
    return scores | {
        "per_case": [c for c in scores["per_case"] if c["case_id"] in keep],
        "grade_table": [r for r in scores["grade_table"] if r["case_id"] in keep],
    }


def bug_detection_arrays(
    scores: dict[str, Any], case_ids: Sequence[str], group: str | None, mode: str = "strict"
) -> tuple[np.ndarray, np.ndarray]:
    """(detected, scorable) must_find bug counts per (case, sample), optionally only one category_group."""
    k = int(scores["samples"])
    index = {c: i for i, c in enumerate(case_ids)}
    num, den = np.zeros((len(case_ids), k)), np.zeros((len(case_ids), k))
    for bug in scores["per_bug"]:
        if not bug.get("must_find", True) or bug["case_id"] not in index:
            continue
        if group is not None and CATEGORY_GROUPS.get(bug["category"], bug["category"]) != group:
            continue
        for s, flag in enumerate(bug[mode]["detected"][:k]):
            if flag is not None:
                num[index[bug["case_id"]], s] += float(flag)
                den[index[bug["case_id"]], s] += 1
    return num, den


def _cost_arrays(reviews: Sequence[ReviewRow], case_ids: Sequence[str]) -> tuple[np.ndarray, np.ndarray]:
    index = {c: i for i, c in enumerate(case_ids)}
    num, den = np.zeros((len(case_ids), 1)), np.zeros((len(case_ids), 1))
    for r in reviews:
        if r.case_id in index:
            num[index[r.case_id], 0] += r.usage.cost_usd
            den[index[r.case_id], 0] += 1
    return num, den


def verdict_label(metric: str, d: dict[str, Any]) -> str:
    """improved / regressed / no detectable change (|delta| within the CI half-width, the MDE proxy)."""
    delta, half = d.get("delta"), d.get("half_width")
    if delta is None:
        return "n/a"
    if half is None or abs(delta) <= half or delta == 0:
        return NO_CHANGE
    better = delta < 0 if metric in LOWER_IS_BETTER else delta > 0
    return "improved" if better else "regressed"


def majority(flags: Sequence[bool | None]) -> bool | None:
    """Majority detection over scorable samples (None when no sample is scorable)."""
    scored = [f for f in flags if f is not None]
    return None if not scored else sum(scored) * 2 > len(scored)


def bug_flips(baseline: dict[str, Any], candidate: dict[str, Any], mode: str = "strict") -> dict[str, Any]:
    """Exact McNemar on per-bug majority detection over the must_find bugs both runs scored, plus the flips."""
    base = {(b["case_id"], b["bug_id"]): b for b in baseline["per_bug"] if b.get("must_find", True)}
    flips, lost, gained, n = [], 0, 0, 0
    for c in candidate["per_bug"]:
        b = base.get((c["case_id"], c["bug_id"]))
        if b is None or not c.get("must_find", True):
            continue
        before, after = majority(b[mode]["detected"]), majority(c[mode]["detected"])
        if before is None or after is None:
            continue
        n += 1
        if before != after:
            lost += int(before)
            gained += int(after)
            flips.append(
                {
                    "case_id": c["case_id"],
                    "bug_id": c["bug_id"],
                    "severity": c["severity"],
                    "category": c["category"],
                    "change": "gained" if after else "lost",
                    "baseline_rate": b[mode]["detect_rate"],
                    "candidate_rate": c[mode]["detect_rate"],
                }
            )
    return {"n_bugs": n, "lost": lost, "gained": gained, "p_value": mcnemar_exact(lost, gained), "flips": flips}


def compare_runs(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_reviews: Sequence[ReviewRow] | None = None,
    candidate_reviews: Sequence[ReviewRow] | None = None,
    n_boot: int = 10000,
    seed: int = 0,
    mode: str = "strict",
) -> dict[str, Any]:
    """Paired deltas (candidate - baseline) on the common cases: headline, gated slices, cost, McNemar, flips."""
    cand_ids = {c["case_id"] for c in candidate["per_case"]}
    common = [c["case_id"] for c in baseline["per_case"] if c["case_id"] in cand_ids]
    metrics = {}
    for name in COMPARE_METRICS:
        d = paired_metric_delta(baseline, candidate, name, mode, n_boot, seed)
        metrics[name] = d | {"label": verdict_label(name, d)}
    if baseline_reviews is not None and candidate_reviews is not None:
        d = paired_ratio_delta(
            *_cost_arrays(baseline_reviews, common), *_cost_arrays(candidate_reviews, common), n_boot, seed
        )
        metrics["cost_usd_per_review"] = d | {"label": verdict_label("cost_usd_per_review", d)}

    slices: dict[str, dict[str, Any]] = {}
    kinds = {c["case_id"]: c["kind"] for c in baseline["per_case"]}
    for kind in sorted({kinds[c] for c in common}):
        ids = [c for c in common if kinds[c] == kind]
        a, b = restrict(baseline, ids), restrict(candidate, ids)
        slices[f"kind:{kind}"] = {}
        for name in GATED_METRICS:
            d = paired_metric_delta(a, b, name, mode, n_boot, seed)
            slices[f"kind:{kind}"][name] = d | {"label": verdict_label(name, d)}
    for group in sorted(candidate.get("slices", {}).get("category_group", {})):
        na, da = bug_detection_arrays(baseline, common, group, mode)
        nb, db = bug_detection_arrays(candidate, common, group, mode)
        keep = (da.sum(axis=1) + db.sum(axis=1)) > 0
        d = paired_ratio_delta(na[keep], da[keep], nb[keep], db[keep], n_boot, seed)
        slices[f"category_group:{group}"] = {"recall": d | {"label": verdict_label("recall", d)}}

    return {
        "mode": mode,
        "n_cases": len(common),
        "n_boot": n_boot,
        "seed": seed,
        "metrics": metrics,
        "slices": slices,
        "mcnemar": bug_flips(baseline, candidate, mode),
    }


def render_compare(result: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any]) -> str:
    def value(scores: dict[str, Any], name: str) -> str:
        if name == "cost_usd_per_review":
            return _f(scores.get("ops", {}).get(name), 4)
        return fmt_metric(scores["metrics"][result["mode"]].get(name))

    rows = [
        (
            name,
            value(baseline["scores"], name),
            value(candidate["scores"], name),
            f"{_f(d['delta'])} [{_f(d['ci_low'])}, {_f(d['ci_high'])}]",
            _f(d["p_two_sided"]),
            _f(d["half_width"]),
            d["label"],
        )
        for name, d in result["metrics"].items()
    ]
    slice_rows = [
        (key, name, f"{_f(d['delta'])} [{_f(d['ci_low'])}, {_f(d['ci_high'])}]", d["n_cases"], d["label"])
        for key, entry in result["slices"].items()
        for name, d in entry.items()
    ]
    mc = result["mcnemar"]
    flips = [
        (
            f["case_id"],
            f["bug_id"],
            f["severity"],
            f["category"],
            f["change"],
            _f(f["baseline_rate"], 2),
            _f(f["candidate_rate"], 2),
        )
        for f in mc["flips"]
    ]
    lines = [
        f"# Compare `{baseline['manifest']['run_id']}` (baseline) -> `{candidate['manifest']['run_id']}` (candidate)",
        "",
        f"Paired cluster bootstrap over {result['n_cases']} common cases ({result['n_boot']} resamples), "
        f"{result['mode']} scoring. Delta = candidate - baseline. MDE = half-width of the delta CI: a delta "
        f"inside it is reported as '{NO_CHANGE}'.",
        "",
        *md_table(("metric", "baseline", "candidate", "delta [95% CI]", "p", "MDE", "verdict"), rows),
        "",
        "## Gated slices",
        "",
        *md_table(("slice", "metric", "delta [95% CI]", "cases", "verdict"), slice_rows),
        "",
        "## Per-bug detection (majority over k)",
        "",
        f"Exact McNemar over {mc['n_bugs']} bugs: {mc['gained']} gained, {mc['lost']} lost, p = {_f(mc['p_value'])}.",
        "",
    ]
    lines += (
        md_table(("case", "bug", "severity", "category", "change", "baseline", "candidate"), flips)
        if flips
        else ["No flips."]
    )
    return "\n".join(lines).rstrip() + "\n"


def cli_compare(args: argparse.Namespace) -> int:
    base_dir, cand_dir = Path(args.baseline_run), Path(args.candidate_run)
    try:
        base_manifest, base_scores = load_run(base_dir)
        cand_manifest, cand_scores = load_run(cand_dir)
    except FileNotFoundError as exc:
        print(f"aireview eval compare: {exc}")
        return EXIT_USAGE
    problems = comparability_problems(base_manifest, cand_manifest)
    if problems:
        print("NOT COMPARABLE:\n  " + "\n  ".join(problems))
        return EXIT_NOT_COMPARABLE
    n_boot = int(cand_scores.get("n_boot", 10000))
    result = compare_runs(
        base_scores,
        cand_scores,
        load_reviews(base_dir),
        load_reviews(cand_dir),
        n_boot,
        int(cand_scores.get("seed", 0)),
    )
    result |= {"baseline_run": base_manifest["run_id"], "candidate_run": cand_manifest["run_id"]}
    out = Path(args.out) if args.out else cand_dir
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "compare.json", result)
    md = render_compare(
        result, {"manifest": base_manifest, "scores": base_scores}, {"manifest": cand_manifest, "scores": cand_scores}
    )
    (out / "compare.md").write_text(md, encoding="utf-8", newline="\n")
    for name, d in result["metrics"].items():
        print(
            f"{name:<24} delta {_f(d['delta']):>7}  CI [{_f(d['ci_low'])}, {_f(d['ci_high'])}]  MDE ±{_f(d['half_width'])}  {d['label']}"
        )
    mc = result["mcnemar"]
    print(f"bugs gained {mc['gained']}, lost {mc['lost']} (McNemar p = {_f(mc['p_value'])})")
    print(f"wrote {out / 'compare.json'} and {out / 'compare.md'}")
    return EXIT_OK
