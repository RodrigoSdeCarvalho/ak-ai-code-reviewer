"""Release gate: a pure function of a run's scores, a promoted baseline and three versioned config files.

Exit codes: 0 PASS / ADVISORY_ONLY, 1 FAIL, 2 NOT_COMPARABLE, 3 USAGE, 4 NOTHING_GATEABLE.
Absolute bars block only once `policy.yaml` acceptance is ACCEPTED; completeness, regression and
newly-missed-critical checks block always. Changing a threshold never needs a re-run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aireview.evals.dataset import resolve_root
from aireview.evals.report import (
    GATE_KEYS,
    LOWER_IS_BETTER,
    comparability_problems,
    compare_runs,
    load_reviews,
    load_run,
    md_table,
    read_json,
    write_json,
)
from aireview.settings import repo_root

EXIT_CODES = {"PASS": 0, "ADVISORY_ONLY": 0, "FAIL": 1, "NOT_COMPARABLE": 2, "USAGE": 3, "NOTHING_GATEABLE": 4}
CheckStatus = Literal["PASS", "FAIL", "ADVISORY_FAIL", "SKIPPED", "INSUFFICIENT_DATA"]
CheckMode = Literal["blocking", "advisory", "blocking_when_accepted"]
CHECK_FAMILIES = ("completeness", "absolute_bars", "regression", "newly_missed_critical", "cost_latency")

# ---------------------------------------------------------------- config files


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Bar(_Strict):
    op: Literal[">=", "<="]
    value: float
    mode: Literal["strict", "location"] = "strict"
    provenance: str
    date: str | None = None


class Completeness(_Strict):
    max_hard_errors: int = 0  # api_error + schema_error rows after retries
    max_soft_error_rate: float = 0.02  # (truncated + refused) / samples
    max_judge_error_rate: float = 0.02  # failed judgments / judge calls
    provenance: str = "design §7"


class NewlyMissed(_Strict):
    severities: list[str] = Field(default_factory=lambda: ["critical", "high"])
    baseline_min_rate: float = 0.66  # detected by the baseline in >= 2/3 of samples
    candidate_max_rate: float = 0.0  # ... and by the candidate in none
    max_lost: int = 0  # how many such bugs a candidate may lose before the check fails
    provenance: str = "design §7"


class CostLatency(_Strict):
    max_cost_ratio: float = 1.5
    max_p95_latency_ratio: float = 1.5
    provenance: str = "design §7"


class Thresholds(_Strict):
    bars: dict[str, Bar] = Field(default_factory=dict)
    completeness: Completeness = Field(default_factory=Completeness)
    newly_missed: NewlyMissed = Field(default_factory=NewlyMissed)
    cost_latency: CostLatency = Field(default_factory=CostLatency)


class Tolerance(_Strict):
    value: float = Field(ge=0)
    provenance: str
    date: str | None = None


class Tolerances(_Strict):
    mode: Literal["strict", "location"] = "strict"
    metrics: dict[str, Tolerance]
    slices: list[str] = Field(default_factory=lambda: ["kind", "category_group"])
    # Headline rule. "demonstrated": fail only when the whole delta CI lies beyond the tolerance (a proven
    # regression). "non_inferiority": fail unless the CI's bad end stays within the tolerance (the candidate
    # must show it is not worse than noise). Slices always use "demonstrated": their CIs are too wide.
    headline_rule: Literal["demonstrated", "non_inferiority"] = "demonstrated"


class Acceptance(_Strict):
    state: Literal["PENDING", "ACCEPTED"] = "PENDING"
    by: str | None = None
    date: str | None = None
    reference: str | None = None


class Policy(_Strict):
    acceptance: Acceptance = Field(default_factory=Acceptance)
    checks: dict[str, CheckMode] = Field(default_factory=dict)
    min_items: int = 6

    def mode_of(self, family: str) -> CheckMode:
        default: CheckMode = "advisory" if family == "cost_latency" else "blocking"
        if family == "absolute_bars":
            default = "blocking_when_accepted"
        return self.checks.get(family, default)

    def blocks(self, family: str) -> bool:
        mode = self.mode_of(family)
        return mode == "blocking" or (mode == "blocking_when_accepted" and self.acceptance.state == "ACCEPTED")


def load_gate_config(gate_dir: Path) -> tuple[Thresholds, Tolerances, Policy]:
    """The three gate files; raises ValueError on a missing or malformed file."""
    out = []
    for name, model in (("thresholds.yaml", Thresholds), ("tolerances.yaml", Tolerances), ("policy.yaml", Policy)):
        path = gate_dir / name
        try:
            out.append(model.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))
        except (OSError, yaml.YAMLError, ValidationError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
    unknown = set(out[2].checks) - set(CHECK_FAMILIES)
    if unknown:
        raise ValueError(f"policy.yaml: unknown check families {sorted(unknown)}; expected {CHECK_FAMILIES}")
    return out[0], out[1], out[2]


# ---------------------------------------------------------------- result


class GateCheck(BaseModel):
    name: str
    status: CheckStatus
    blocking: bool
    value: Any = None
    bar: Any = None
    provenance: str | None = None
    detail: str | None = None


class GateResult(BaseModel):
    decision: str
    exit_code: int
    run_id: str | None = None
    baseline_run_id: str | None = None
    acceptance: str
    regression_basis: str  # paired | unpaired-ci-overlap | none
    comparability_problems: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    checks: list[GateCheck]


def _check(
    name: str,
    failed: bool,
    blocking: bool,
    value: Any,
    bar: Any,
    provenance: str | None,
    detail: str | None = None,
) -> GateCheck:
    status: CheckStatus = "PASS" if not failed else ("FAIL" if blocking else "ADVISORY_FAIL")
    return GateCheck(
        name=name, status=status, blocking=blocking, value=value, bar=bar, provenance=provenance, detail=detail
    )


def _skip(name: str, blocking: bool, detail: str, status: CheckStatus = "SKIPPED", **kw: Any) -> GateCheck:
    return GateCheck(name=name, status=status, blocking=blocking, detail=detail, **kw)


def _r(x: float | None) -> float | None:
    return None if x is None else round(float(x), 4)


# ---------------------------------------------------------------- checks


def completeness_checks(
    scores: dict[str, Any], manifest: dict[str, Any], t: Completeness, blocking: bool
) -> list[GateCheck]:
    counts = scores.get("status_counts", {})
    total = scores.get("total_samples", 0) or 0
    incomplete = bool(manifest.get("extra", {}).get("incomplete")) or counts.get("missing", 0) > 0
    hard = counts.get("api_error", 0) + counts.get("schema_error", 0)
    soft = counts.get("truncated", 0) + counts.get("refused", 0)
    soft_rate = soft / total if total else 0.0
    ops = scores.get("ops", {})
    calls, judge_errors = ops.get("judge_calls", 0), ops.get("judge_errors", 0)
    judge_missing = scores["metrics"]["strict"].get("judge_missing", 0)
    judge_rate = judge_errors / calls if calls else 0.0
    return [
        _check(
            "completeness.run_complete",
            incomplete,
            blocking,
            {"incomplete": bool(manifest.get("extra", {}).get("incomplete")), "missing": counts.get("missing", 0)},
            "no missing samples",
            t.provenance,
            "budget stop or missing rows" if incomplete else None,
        ),
        _check(
            "completeness.hard_errors",
            hard > t.max_hard_errors,
            blocking,
            hard,
            f"<= {t.max_hard_errors}",
            t.provenance,
        ),
        _check(
            "completeness.soft_errors",
            soft_rate > t.max_soft_error_rate,
            blocking,
            _r(soft_rate),
            f"<= {t.max_soft_error_rate}",
            t.provenance,
            f"{soft} truncated/refused of {total}",
        ),
        _check(
            "completeness.judge",
            judge_missing > 0 or judge_rate > t.max_judge_error_rate,
            blocking,
            {"missing": judge_missing, "error_rate": _r(judge_rate)},
            f"0 missing, error rate <= {t.max_judge_error_rate}",
            t.provenance,
            "missing judge cassettes or failed judgments bias strict scores down"
            if judge_missing or judge_errors
            else None,
        ),
    ]


def _passes(value: float, op: str, bar: float) -> bool:
    return value >= bar if op == ">=" else value <= bar


def absolute_checks(scores: dict[str, Any], thresholds: Thresholds, policy: Policy) -> list[GateCheck]:
    blocking = policy.blocks("absolute_bars")
    out = []
    for metric, bar in thresholds.bars.items():
        name = f"absolute.{metric}"
        m = scores["metrics"][bar.mode].get(metric)
        bar_text = f"{bar.op} {bar.value}"
        if m is None or m.get("value") is None:
            out.append(_skip(name, blocking, "metric undefined for this run", bar=bar_text, provenance=bar.provenance))
        elif m["n"] < policy.min_items:
            out.append(
                _skip(
                    name,
                    blocking,
                    f"n={m['n']} < {policy.min_items}",
                    "INSUFFICIENT_DATA",
                    value=_r(m["value"]),
                    bar=bar_text,
                    provenance=bar.provenance,
                )
            )
        else:
            detail = None if blocking else f"advisory: acceptance {policy.acceptance.state}"
            out.append(
                _check(
                    name,
                    not _passes(m["value"], bar.op, bar.value),
                    blocking,
                    _r(m["value"]),
                    bar_text,
                    bar.provenance,
                    detail,
                )
            )
    return out


def _regressed(metric: str, lo: float, hi: float, tol: float, rule: str = "demonstrated") -> bool:
    """`demonstrated`: the interval lies entirely beyond the tolerance in the bad direction.
    `non_inferiority`: the interval's bad end reaches beyond the tolerance."""
    if rule == "non_inferiority":
        return hi > tol if metric in LOWER_IS_BETTER else lo < -tol
    return lo > tol if metric in LOWER_IS_BETTER else hi < -tol


def _rule_bar(metric: str, tol: float, rule: str) -> str:
    worse = "above +" if metric in LOWER_IS_BETTER else "below -"
    if rule == "non_inferiority":
        return f"delta CI bad end not {worse}{tol} (non-inferiority)"
    return f"delta CI not entirely {worse}{tol}"


def _slice_n(scores: dict[str, Any], key: str, metric: str, mode: str) -> int | None:
    dim, value = key.split(":", 1)
    entry = scores.get("slices", {}).get(dim, {}).get(value)
    if entry is None:
        return None
    m = entry[mode].get(metric)
    return None if m is None else m["n"]


def paired_regression_checks(
    scores: dict[str, Any], compare: dict[str, Any], tolerances: Tolerances, policy: Policy
) -> list[GateCheck]:
    """Paired-bootstrap delta CI vs tolerance, headline and every gated slice."""
    blocking = policy.blocks("regression")
    targets: list[tuple[str, str, dict[str, Any], int | None, str]] = []
    for metric, d in compare["metrics"].items():
        if metric in tolerances.metrics:
            m = scores["metrics"][tolerances.mode].get(metric)
            targets.append((f"regression.{metric}", metric, d, None if m is None else m["n"], tolerances.headline_rule))
    for key, entry in compare.get("slices", {}).items():
        if key.split(":", 1)[0] not in tolerances.slices:
            continue
        for metric, d in entry.items():
            if metric in tolerances.metrics and d.get("delta") is not None:
                targets.append(
                    (
                        f"regression.{key}.{metric}",
                        metric,
                        d,
                        _slice_n(scores, key, metric, tolerances.mode),
                        "demonstrated",
                    )
                )
    out = []
    for name, metric, d, n, rule in targets:
        tol = tolerances.metrics[metric]
        bar = _rule_bar(metric, tol.value, rule)
        if d.get("delta") is None or d.get("ci_low") is None:
            out.append(
                _skip(name, blocking, "delta undefined (metric has no denominator)", bar=bar, provenance=tol.provenance)
            )
        elif n is not None and n < policy.min_items:
            out.append(
                _skip(
                    name,
                    blocking,
                    f"n={n} < {policy.min_items}",
                    "INSUFFICIENT_DATA",
                    value=_r(d["delta"]),
                    bar=bar,
                    provenance=tol.provenance,
                )
            )
        else:
            detail = (
                f"paired delta {d['delta']:+.3f} [{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] over {d['n_cases']} cases"
            )
            out.append(
                _check(
                    name,
                    _regressed(metric, d["ci_low"], d["ci_high"], tol.value, rule),
                    blocking,
                    _r(d["delta"]),
                    bar,
                    tol.provenance,
                    detail,
                )
            )
    return out


def unpaired_regression_checks(
    scores: dict[str, Any], summary: dict[str, Any], tolerances: Tolerances, policy: Policy
) -> list[GateCheck]:
    """Fallback without the baseline's per-case data: the candidate CI must not lie beyond the baseline CI ± tol."""
    blocking = policy.blocks("regression")
    mode = tolerances.mode
    pairs: list[tuple[str, str, dict[str, Any] | None, dict[str, Any] | None]] = []
    for metric in tolerances.metrics:
        pairs.append(
            (f"regression.{metric}", metric, summary["metrics"][mode].get(metric), scores["metrics"][mode].get(metric))
        )
    for dim in tolerances.slices:
        for value, entry in scores.get("slices", {}).get(dim, {}).items():
            base_entry = summary.get("slices", {}).get(dim, {}).get(value)
            for metric in tolerances.metrics:
                if entry[mode].get(metric, {}).get("value") is not None:
                    base = base_entry[mode].get(metric) if base_entry else None
                    pairs.append((f"regression.{dim}:{value}.{metric}", metric, base, entry[mode][metric]))
    out = []
    for name, metric, base, cand in pairs:
        tol = tolerances.metrics[metric]
        bar = f"CI not entirely beyond baseline CI by {tol.value}"
        if (
            not base
            or not cand
            or None in (base.get("ci_low"), base.get("ci_high"), cand.get("ci_low"), cand.get("ci_high"))
        ):
            out.append(_skip(name, blocking, "unpaired fallback: metric undefined", bar=bar, provenance=tol.provenance))
            continue
        if cand["n"] < policy.min_items:
            out.append(
                _skip(
                    name,
                    blocking,
                    f"n={cand['n']} < {policy.min_items}",
                    "INSUFFICIENT_DATA",
                    value=_r(cand["value"]),
                    bar=bar,
                    provenance=tol.provenance,
                )
            )
            continue
        # Express the gap as an interval of (candidate - baseline) built from the two CIs.
        lo, hi = cand["ci_low"] - base["ci_high"], cand["ci_high"] - base["ci_low"]
        detail = (
            f"unpaired CI-overlap fallback (baseline run dir not available): candidate {cand['value']:.3f} "
            f"[{cand['ci_low']:.3f}, {cand['ci_high']:.3f}] vs baseline {base['value']:.3f} [{base['ci_low']:.3f}, {base['ci_high']:.3f}]"
        )
        out.append(
            _check(
                name,
                _regressed(metric, lo, hi, tol.value),
                blocking,
                _r(cand["value"] - base["value"]),
                bar,
                tol.provenance,
                detail,
            )
        )
    return out


def newly_missed_check(
    scores: dict[str, Any], summary: dict[str, Any], t: NewlyMissed, mode: str, blocking: bool
) -> GateCheck:
    base = {(b["case_id"], b["bug_id"]): b for b in summary.get("per_bug", [])}
    lost = []
    for bug in scores.get("per_bug", []):
        if not bug.get("must_find", True) or bug["severity"] not in t.severities:
            continue
        b = base.get((bug["case_id"], bug["bug_id"]))
        before, after = (b or {}).get(mode, {}).get("detect_rate"), bug[mode]["detect_rate"]
        if before is not None and after is not None and before >= t.baseline_min_rate and after <= t.candidate_max_rate:
            lost.append(f"{bug['case_id']}/{bug['bug_id']}")
    return _check(
        "newly_missed_critical",
        len(lost) > t.max_lost,
        blocking,
        len(lost),
        f"<= {t.max_lost} {'/'.join(t.severities)} bugs with baseline rate >= {t.baseline_min_rate} and candidate rate <= {t.candidate_max_rate}",
        t.provenance,
        ", ".join(lost) or None,
    )


def cost_latency_checks(
    scores: dict[str, Any], summary: dict[str, Any], t: CostLatency, blocking: bool
) -> list[GateCheck]:
    out = []
    for name, key, ratio in (
        ("cost.per_review", "cost_usd_per_review", t.max_cost_ratio),
        ("latency.p95", "latency_p95_ms", t.max_p95_latency_ratio),
    ):
        base, cand = summary.get("ops", {}).get(key), scores.get("ops", {}).get(key)
        if not base or cand is None:
            out.append(
                _skip(
                    name,
                    blocking,
                    "not measured in baseline or candidate",
                    bar=f"<= {ratio}x baseline",
                    provenance=t.provenance,
                )
            )
            continue
        out.append(
            _check(
                name,
                cand > ratio * base,
                blocking,
                _r(cand / base),
                f"<= {ratio}x baseline",
                t.provenance,
                f"{cand:.4g} vs {base:.4g}",
            )
        )
    return out


# ---------------------------------------------------------------- decision


def decide(
    scores: dict[str, Any],
    manifest: dict[str, Any],
    baseline: dict[str, Any] | None,
    thresholds: Thresholds | dict[str, Any],
    tolerances: Tolerances | dict[str, Any],
    policy: Policy | dict[str, Any],
    compare: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> GateResult:
    """The gate decision. `compare` = report.compare_runs(baseline scores, candidate scores) when the
    baseline run dir is available and unchanged since promotion (paired); otherwise regression falls back
    to baseline.json CIs.

    Precedence: NOTHING_GATEABLE > FAIL > NOT_COMPARABLE > ADVISORY_ONLY > PASS. A blocking failure that
    needs no baseline (completeness, accepted absolute bars) is a FAIL even when the baseline is not
    comparable, so an incomplete or errored run can never be promoted as "not comparable"."""
    th = Thresholds.model_validate(thresholds) if isinstance(thresholds, dict) else thresholds
    tol = Tolerances.model_validate(tolerances) if isinstance(tolerances, dict) else tolerances
    pol = Policy.model_validate(policy) if isinstance(policy, dict) else policy

    checks = completeness_checks(scores, manifest, th.completeness, pol.blocks("completeness"))
    checks += absolute_checks(scores, th, pol)
    problems: list[str] = []
    basis = "none"
    if baseline is None:
        checks.append(_skip("regression", pol.blocks("regression"), "no baseline promoted yet"))
    else:
        problems = comparability_problems(baseline["manifest"], manifest, GATE_KEYS)
        summary = baseline["scores_summary"]
        if problems:
            checks.append(_skip("regression", pol.blocks("regression"), "not comparable: " + "; ".join(problems)))
        else:
            if compare is not None:
                basis = "paired"
                checks += paired_regression_checks(scores, compare, tol, pol)
            else:
                basis = "unpaired-ci-overlap"
                checks += unpaired_regression_checks(scores, summary, tol, pol)
            checks.append(
                newly_missed_check(scores, summary, th.newly_missed, tol.mode, pol.blocks("newly_missed_critical"))
            )
            checks += cost_latency_checks(scores, summary, th.cost_latency, pol.blocks("cost_latency"))

    if scores.get("scorable_samples", 0) == 0:
        decision = "NOTHING_GATEABLE"
    elif any(c.status == "FAIL" for c in checks):
        decision = "FAIL"
    elif problems:
        decision = "NOT_COMPARABLE"
    elif any(c.status == "ADVISORY_FAIL" for c in checks):
        decision = "ADVISORY_ONLY"
    else:
        decision = "PASS"
    return GateResult(
        decision=decision,
        exit_code=EXIT_CODES[decision],
        run_id=manifest.get("run_id"),
        baseline_run_id=baseline.get("run_id") if baseline else None,
        acceptance=pol.acceptance.state,
        regression_basis=basis,
        comparability_problems=problems,
        notes=list(notes or []),
        checks=checks,
    )


# ---------------------------------------------------------------- baseline.json


def scores_summary(scores: dict[str, Any]) -> dict[str, Any]:
    """What the gate needs from a baseline when its run dir is gone: headline, slices, per-bug rates, ops."""
    return {
        "metrics": scores["metrics"],
        "slices": scores.get("slices", {}),
        "per_bug": [
            {
                k: b[k]
                for k in (
                    "case_id",
                    "bug_id",
                    "kind",
                    "file",
                    "line_start",
                    "line_end",
                    "severity",
                    "category",
                    "must_find",
                    "strict",
                    "location",
                )
            }
            for b in scores.get("per_bug", [])
        ],
        "ops": scores.get("ops", {}),
        "status_counts": scores.get("status_counts", {}),
        "scorable_samples": scores.get("scorable_samples"),
        "total_samples": scores.get("total_samples"),
        "counts": scores.get("counts", {}),
        "samples": scores.get("samples"),
    }


def scores_digest(scores: dict[str, Any]) -> str:
    """sha256 of the canonical scores JSON: detects a baseline run dir rescored after promotion."""
    canonical = json.dumps(scores, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _portable(path: Path) -> str:
    """Repo-relative posix path when the run lives in the repo, else absolute."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root()).as_posix()
    except ValueError:
        return resolved.as_posix()


def baseline_record(
    run_dir: Path, manifest: dict[str, Any], scores: dict[str, Any], by: str, reason: str, gate: dict[str, Any] | None
) -> dict[str, Any]:
    return {
        "run_id": manifest["run_id"],
        "run_dir": _portable(run_dir),
        "promoted_by": by,
        "reason": reason,
        "promoted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "gate_decision": (gate or {}).get("decision"),
        "scores_sha256": scores_digest(scores),
        "manifest": manifest,
        "scores_summary": scores_summary(scores),
    }


# ---------------------------------------------------------------- CLI


class GateUsageError(ValueError):
    """Bad arguments or malformed gate config / baseline (exit 3)."""


def evaluate(run_dir: Path, baseline_path: Path, gate_dir: Path) -> GateResult:
    """Load everything the gate needs from disk and decide (pairing with the baseline run when available)."""
    try:
        manifest, scores = load_run(run_dir)
        thresholds, tolerances, policy = load_gate_config(resolve_root(gate_dir))
        baseline = read_json(baseline_path) if baseline_path.is_file() else None
    except (FileNotFoundError, ValueError) as exc:
        raise GateUsageError(str(exc)) from exc
    if baseline is not None and not {"manifest", "scores_summary"} <= baseline.keys():
        raise GateUsageError(f"{baseline_path}: missing manifest / scores_summary")
    compare = None
    notes: list[str] = []
    if baseline is not None and not comparability_problems(baseline["manifest"], manifest, GATE_KEYS):
        base_dir = resolve_root(baseline.get("run_dir") or "")
        live = (
            baseline.get("run_dir") and (base_dir / "manifest.json").is_file() and (base_dir / "scores.json").is_file()
        )
        drift = None
        if live:
            base_manifest, base_scores = load_run(base_dir)
            drift = baseline_drift(baseline, base_manifest, base_scores)
            if drift:
                notes.append(
                    f"baseline run dir {baseline['run_dir']} changed since promotion ({drift}); "
                    "regression uses the promoted baseline.json snapshot (unpaired)"
                )
        if live and not drift:
            reviews = (
                (load_reviews(base_dir), load_reviews(run_dir))
                if (base_dir / "reviews.jsonl").exists()
                else (None, None)
            )
            compare = compare_runs(
                base_scores,
                scores,
                *reviews,
                n_boot=int(scores.get("n_boot", 10000)),
                seed=int(scores.get("seed", 0)),
                mode=tolerances.mode,
            )
    return decide(scores, manifest, baseline, thresholds, tolerances, policy, compare, notes)


def baseline_drift(baseline: dict[str, Any], live_manifest: dict[str, Any], live_scores: dict[str, Any]) -> str | None:
    """Why the baseline's live run dir no longer matches the promoted snapshot (None = unchanged)."""
    problems = comparability_problems(baseline["manifest"], live_manifest, GATE_KEYS)
    if problems:
        return "; ".join(problems)
    digest = baseline.get("scores_sha256")
    if digest is not None and digest != scores_digest(live_scores):
        return "scores.json differs from the promoted one"
    return None


def render_gate(result: GateResult) -> str:
    rows = [
        (
            c.name,
            c.status,
            "yes" if c.blocking else "no",
            c.value if c.value is not None else "",
            c.bar or "",
            c.provenance or "",
            c.detail or "",
        )
        for c in result.checks
    ]
    lines = [
        f"# Gate: **{result.decision}** (exit {result.exit_code})",
        "",
        f"Run `{result.run_id}` vs baseline `{result.baseline_run_id}`; regression basis: {result.regression_basis}; "
        f"absolute bars acceptance: {result.acceptance}.",
        "",
    ]
    if result.comparability_problems:
        lines += ["Not comparable:", *[f"- {p}" for p in result.comparability_problems], ""]
    if result.notes:
        lines += ["Notes:", *[f"- {n}" for n in result.notes], ""]
    lines += md_table(("check", "status", "blocking", "value", "bar", "provenance", "detail"), rows)
    return "\n".join(lines) + "\n"


def write_gate(run_dir: Path, result: GateResult) -> None:
    write_json(run_dir / "gate.json", result.model_dump(mode="json"))
    (run_dir / "gate.md").write_text(render_gate(result), encoding="utf-8", newline="\n")


def cli_gate(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    baseline_path = resolve_root(args.baseline)
    try:
        result = evaluate(run_dir, baseline_path, Path(args.gate_dir))
    except GateUsageError as exc:
        print(f"aireview eval gate: {exc}", file=sys.stderr)
        return EXIT_CODES["USAGE"]
    if not baseline_path.is_file():
        print(f"note: no baseline at {baseline_path}; regression checks skipped")
    write_gate(run_dir, result)
    print(render_gate(result))
    return result.exit_code


def cli_promote(args: argparse.Namespace) -> int:
    """Gate the run again against the current baseline and gate config (a gate.json already in the run
    dir may be stale), then write baseline.json unless a blocking check failed."""
    run_dir = Path(args.run)
    baseline_path = resolve_root(args.baseline)
    try:
        manifest, scores = load_run(run_dir)
        result = evaluate(run_dir, baseline_path, Path(getattr(args, "gate_dir", None) or "evals/gate"))
    except (FileNotFoundError, GateUsageError) as exc:
        print(f"aireview eval promote: {exc}", file=sys.stderr)
        return EXIT_CODES["USAGE"]
    write_gate(run_dir, result)
    gate = result.model_dump(mode="json")
    decision = result.decision
    failed = [c.name for c in result.checks if c.status == "FAIL"]
    if decision == "NOTHING_GATEABLE":
        print("refusing to promote: the run has no scorable samples")
        return EXIT_CODES["FAIL"]
    if failed and not args.accept_regression:
        print(
            f"refusing to promote: blocking checks failed ({', '.join(failed)}); "
            "re-run with --accept-regression to override (recorded in baseline.json)"
        )
        return EXIT_CODES["FAIL"]
    if decision == "NOT_COMPARABLE":
        print("warning: the run is not comparable with the current baseline; promoting starts a new comparison series")
    record = baseline_record(run_dir, manifest, scores, args.by, args.reason, gate)
    record["accepted_regression"] = bool(failed and args.accept_regression)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(baseline_path, record)
    print(f"promoted {manifest['run_id']} (gate {decision}) -> {baseline_path}")
    return EXIT_CODES["PASS"]
