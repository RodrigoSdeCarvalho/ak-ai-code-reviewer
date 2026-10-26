"""`aireview eval run` / `score`: a reviewer config over cases x k samples -> judged, scored run dir.

Model calls go through the cassette layer (`replay` reads, `record` calls and writes). Synthetic
backends (oracle/null/spam) and the static baseline need no model; synthetic runs use the exact-match
judge, every other backend the LLM judge.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import yaml

from aireview import __version__
from aireview.evals.baselines import SYNTHETIC_BACKENDS, ExactMatchJudge, synthetic_review
from aireview.evals.dataset import dataset_hash, dataset_version, load_dataset, read_case_diff, resolve_root, select
from aireview.evals.judge import (
    JUDGE_PROMPT_VERSION,
    TRIAGE_PROMPT_VERSION,
    Judge,
    JudgeItem,
    TriageItem,
    candidate_items,
)
from aireview.evals.matching import MAX_JUDGE_TOL
from aireview.evals.metrics import compute_scores
from aireview.evals.report import (
    fmt_metric,
    load_judgments,
    load_reviews,
    read_json,
    read_jsonl,
    render,
    write_json,
    write_jsonl,
)
from aireview.evals.schema import Case, Judgment, ReviewerConfig, ReviewRow, RunManifest
from aireview.llm.base import LLMClient, LLMRequest
from aireview.llm.cassette import (
    BudgetExceeded,
    BudgetTracker,
    CassetteConflict,
    CassetteStore,
    conflict_message,
    make_client,
)
from aireview.models import Review, ReviewStatus
from aireview.reviewer.reviewer import build_request, load_config, parse_response, prompt_hash, resolve_config
from aireview.settings import DEFAULT_JUDGE_MODEL, cost_usd, repo_root

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 3
LLM_BACKENDS = ("anthropic", "claude-cli")
KNOWN_BACKENDS = (*LLM_BACKENDS, "static", *SYNTHETIC_BACKENDS)
CHARS_PER_TOKEN = 3.5
REVIEW_OUTPUT_TOKENS = 2500
JUDGE_PAIRS_PER_REVIEW = 3
JUDGE_INPUT_TOKENS, JUDGE_OUTPUT_TOKENS = 1500, 300
DEFAULT_SCORE_BUDGET_USD = 2.0  # `eval score --mode record`: judge + triage calls only
CHUNK_SIZE = 16  # sync/replay calls per complete_many, so a budget stop keeps the finished chunks
RUN_FILES = (
    "manifest.json",
    "reviews.jsonl",
    "errors.jsonl",
    "judgments.jsonl",
    "triage.jsonl",
    "scores.json",
    "report.md",
    "gate.json",
    "gate.md",
    "compare.json",
    "compare.md",
)


class JudgeLike(Protocol):
    model: str

    def judge_many(self, items: Sequence[JudgeItem]) -> list[Judgment]: ...


@dataclass
class RunPlan:
    """Everything that defines a run, independent of how the model is reached."""

    run_id: str
    run_dir: Path
    config: ReviewerConfig
    cases: list[tuple[Case, Path]]
    dataset_root: Path
    split: str
    samples: int
    mode: str
    batch: bool = False
    tolerance: int = 3
    triage_fp: bool = False
    n_boot: int = 10000
    sample_offset: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunResult:
    manifest: RunManifest
    scores: dict[str, Any]
    rows: list[ReviewRow]
    judgments: list[Judgment]
    incomplete: bool


# ---------------------------------------------------------------- helpers


def now_utc() -> datetime:
    return datetime.now(UTC)


def default_run_id(config: ReviewerConfig, split: str, samples: int, mode: str, when: datetime) -> str:
    return f"{config.name}-{split}-k{samples}-{mode}-{when:%Y%m%dT%H%M%S}"


def config_hash(config: ReviewerConfig) -> str:
    """sha256 of the canonical config JSON."""
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def git_state(root: Path | None = None) -> tuple[str | None, bool | None]:
    """(HEAD sha, dirty flag) of the repo, or (None, None) outside git."""
    cwd = root or repo_root()
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, capture_output=True, text=True, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return sha.stdout.strip() or None, bool(status.stdout.strip())


def failure_class(row: ReviewRow) -> str:
    """The original error class (e.g. cassette_missing, timeout) when the error names one, else the status."""
    if row.error and ":" in row.error:
        head = row.error.split(":", 1)[0].strip()
        if head.replace("_", "").isalnum():
            return head
    return row.status.value


def row_from_review(
    case_id: str,
    sample: int,
    review: Review,
    served_model: str | None = None,
    key: str | None = None,
    attempts: int | None = None,
) -> ReviewRow:
    return ReviewRow(
        case_id=case_id,
        sample=sample,
        status=review.status,
        findings=review.findings,
        out_of_scope_findings=review.out_of_scope_findings,
        suppressed_findings=review.suppressed_findings,
        usage=review.usage,
        served_model=served_model,
        cassette_key=key,
        attempts=attempts,
        error=review.error,
    )


def _chunks[T](items: Sequence[T], size: int | None) -> list[Sequence[T]]:
    if not items:
        return []
    if size is None:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


# ---------------------------------------------------------------- budget


def estimate_cost(
    requests: Sequence[LLMRequest],
    judge_model: str | None,
    batch: bool = False,
    judged_reviews: int | None = None,
    reviewer_batch: bool | None = None,
) -> dict[str, Any]:
    """Pre-run cost estimate: input ~ chars/3.5, output ~2500 tokens per review, judge ~3 pairs per review.

    `judged_reviews` overrides the number of reviews the judge sees (for backends with no model requests);
    `reviewer_batch` overrides `batch` for the reviewer (the claude-cli backend never gets the discount).
    An unpriced model raises KeyError: a silent $0 would let an unbounded run past the budget check.
    """
    reviewer_discount = batch if reviewer_batch is None else reviewer_batch
    reviewer_usd, tokens_in = 0.0, 0
    for r in requests:
        n_in = int((len(r.system) + len(r.user)) / CHARS_PER_TOKEN)
        tokens_in += n_in
        reviewer_usd += cost_usd(r.model, n_in, REVIEW_OUTPUT_TOKENS, batch=reviewer_discount)
    pairs = (len(requests) if judged_reviews is None else judged_reviews) * JUDGE_PAIRS_PER_REVIEW
    judge_usd = 0.0
    if judge_model is not None:
        judge_usd = pairs * cost_usd(judge_model, JUDGE_INPUT_TOKENS, JUDGE_OUTPUT_TOKENS, batch=batch)
    return {
        "reviews": len(requests),
        "reviewer_input_tokens": tokens_in,
        "reviewer_output_tokens": len(requests) * REVIEW_OUTPUT_TOKENS,
        "reviewer_usd": reviewer_usd,
        "judge_pairs": pairs,
        "judge_usd": judge_usd,
        "total_usd": reviewer_usd + judge_usd,
        "batch": batch,
        "reviewer_batch": reviewer_discount,
    }


def confirm(question: str, read: Callable[[str], str] = input) -> bool:
    try:
        return read(f"{question} [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


# ---------------------------------------------------------------- reviews


def reviewer_requests(plan: RunPlan) -> list[tuple[Case, Path, int, str, LLMRequest]]:
    """(case, case_dir, sample, diff, request) for every (case, sample), in case then sample order.

    The request's sample index is `sample_offset + sample`, so an independent re-record of the same
    config gets its own cassettes instead of overwriting another run's.
    """
    jobs = []
    for case, case_dir in plan.cases:
        diff = read_case_diff(case_dir)
        for s in range(plan.samples):
            request = build_request(diff, case_dir / "after", plan.config, sample=plan.sample_offset + s)
            jobs.append((case, case_dir, s, diff, request))
    return jobs


def run_reviews(
    plan: RunPlan, client: LLMClient | None, budget: BudgetTracker | None = None, chunk_size: int | None = CHUNK_SIZE
) -> tuple[list[ReviewRow], bool]:
    """Review rows for every (case, sample) and whether the budget stopped the run early."""
    backend = plan.config.backend
    rows: list[ReviewRow] = []
    if backend in SYNTHETIC_BACKENDS or backend == "static":
        for case, case_dir in plan.cases:
            diff = read_case_diff(case_dir)
            if backend == "static":
                from aireview.reviewer.static_baseline import static_review

                review = static_review(diff, case_dir / "after")
            else:
                review = synthetic_review(backend, case, diff)
            rows.extend(row_from_review(case.id, s, review) for s in range(plan.samples))
        return rows, False
    if backend == "claude-cli":
        from aireview.reviewer.claude_cli import claude_cli_review

        for case, case_dir in plan.cases:
            diff = read_case_diff(case_dir)
            for s in range(plan.samples):
                if budget is not None:
                    try:
                        budget.check()
                    except BudgetExceeded:
                        return rows, True
                review = claude_cli_review(diff, case_dir / "after", plan.config)
                if budget is not None:
                    budget.add(review.usage.cost_usd)
                rows.append(row_from_review(case.id, s, review, served_model=plan.config.model))
        return rows, False
    if backend != "anthropic":
        raise ValueError(f"unknown backend {backend!r}; expected one of {KNOWN_BACKENDS}")
    if client is None:
        raise ValueError("the anthropic backend needs an LLM client")
    for chunk in _chunks(reviewer_requests(plan), chunk_size):
        try:
            responses = client.complete_many([job[4] for job in chunk])
        except BudgetExceeded:
            return rows, True
        for (case, _, s, diff, request), response in zip(chunk, responses, strict=True):
            review = parse_response(response, diff, plan.config)
            rows.append(row_from_review(case.id, s, review, response.served_model, request.key(), response.attempts))
    return rows, False


# ---------------------------------------------------------------- judging


def judge_items(cases: Sequence[tuple[Case, Path]], rows: Sequence[ReviewRow]) -> list[JudgeItem]:
    """Every (finding, bug) location candidate within MAX_JUDGE_TOL of the scorable rows."""
    by_id = {case.id: (case, case_dir) for case, case_dir in cases}
    items: list[JudgeItem] = []
    for row in rows:
        if row.status != ReviewStatus.ok or row.case_id not in by_id:
            continue
        case, case_dir = by_id[row.case_id]
        items.extend(candidate_items(case, case_dir, row.sample, row.findings, MAX_JUDGE_TOL))
    return items


def run_judge(
    judge: JudgeLike, items: Sequence[JudgeItem], chunk_size: int | None = CHUNK_SIZE
) -> tuple[list[Judgment], bool]:
    """Judgments for the items and whether the budget stopped judging early."""
    out: list[Judgment] = []
    for chunk in _chunks(items, chunk_size):
        try:
            out.extend(judge.judge_many(chunk))
        except BudgetExceeded:
            return out, True
    return out, False


def triage_items(
    cases: Sequence[tuple[Case, Path]], rows: Sequence[ReviewRow], scores: dict[str, Any]
) -> list[TriageItem]:
    """Findings that are strict false positives, for the advisory FP triage."""
    by_id = {case.id: (case, case_dir) for case, case_dir in cases}
    by_key = {(r.case_id, r.sample): r for r in rows}
    items = []
    for case_entry in scores["per_case"]:
        case, case_dir = by_id[case_entry["case_id"]]
        for sample in case_entry["samples"]:
            outcome, row = sample.get("strict"), by_key.get((case.id, sample["sample"]))
            if outcome is None or row is None:
                continue
            for i, kind in enumerate(outcome["finding_outcomes"]):
                if kind == "fp":
                    items.append(TriageItem(case, case_dir, row.sample, i, row.findings[i]))
    return items


# ---------------------------------------------------------------- the run


def build_manifest(plan: RunPlan, judge: JudgeLike, incomplete: bool) -> RunManifest:
    sha, dirty = git_state()
    config = plan.config
    p_hash = prompt_hash(config.prompt_version) if config.backend in LLM_BACKENDS and config.prompt_version else None
    return RunManifest(
        run_id=plan.run_id,
        created_at=now_utc().isoformat(timespec="seconds"),
        aireview_version=__version__,
        git_sha=sha,
        git_dirty=dirty,
        dataset_version=dataset_version(plan.dataset_root),
        dataset_hash=dataset_hash(plan.dataset_root),
        split=plan.split,
        case_ids=[case.id for case, _ in plan.cases],
        samples=plan.samples,
        mode=plan.mode,
        batch=plan.batch,
        config=config,
        config_hash=config_hash(config),
        prompt_hash=p_hash,
        judge_model=judge.model,
        judge_prompt_version=getattr(judge, "prompt_version", JUDGE_PROMPT_VERSION),
        tolerance=plan.tolerance,
        sample_offset=plan.sample_offset,
        extra={"dataset": plan.dataset_root.as_posix(), "n_boot": plan.n_boot, **plan.extra, "incomplete": incomplete},
    )


def error_rows(rows: Sequence[ReviewRow], case_ids: Sequence[str] = (), samples: int = 0) -> list[dict[str, Any]]:
    """Every (case, sample) without scorable output: non-ok rows, then rows never produced (budget stop)."""
    out: list[dict[str, Any]] = [
        {
            "case_id": r.case_id,
            "sample": r.sample,
            "status": r.status.value,
            "failure_class": failure_class(r),
            "attempts": r.attempts,
            "error": r.error,
        }
        for r in rows
        if r.status != ReviewStatus.ok
    ]
    have = {(r.case_id, r.sample) for r in rows}
    out += [
        {
            "case_id": case_id,
            "sample": s,
            "status": "missing",
            "failure_class": "missing",
            "attempts": None,
            "error": "no review row: the run stopped before this sample",
        }
        for case_id in case_ids
        for s in range(samples)
        if (case_id, s) not in have
    ]
    return out


def write_run(
    run_dir: Path,
    manifest: RunManifest,
    rows: Sequence[ReviewRow],
    judgments: Sequence[Judgment],
    scores: dict[str, Any],
    triage: Sequence[dict[str, Any]] | None = None,
) -> None:
    """All run artefacts; stale files from an earlier run with the same id are removed first."""
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in RUN_FILES:
        (run_dir / name).unlink(missing_ok=True)
    write_json(run_dir / "manifest.json", manifest.model_dump(mode="json"))
    write_jsonl(run_dir / "reviews.jsonl", rows)
    write_jsonl(run_dir / "errors.jsonl", error_rows(rows, manifest.case_ids, manifest.samples))
    write_jsonl(run_dir / "judgments.jsonl", judgments)
    if triage is not None:
        write_jsonl(run_dir / "triage.jsonl", triage)
    write_json(run_dir / "scores.json", scores)
    report = render(scores, manifest, list(rows), triage)
    (run_dir / "report.md").write_text(report, encoding="utf-8", newline="\n")


def execute(
    plan: RunPlan,
    reviewer_client: LLMClient | None,
    judge: JudgeLike,
    budget: BudgetTracker | None = None,
    chunk_size: int | None = CHUNK_SIZE,
) -> RunResult:
    """Review, judge, (triage,) score and write the run dir. A budget stop keeps what finished."""
    rows, stopped = run_reviews(plan, reviewer_client, budget, chunk_size)
    judgments: list[Judgment] = []
    if not stopped:
        judgments, stopped = run_judge(judge, judge_items(plan.cases, rows), chunk_size)
    scores = compute_scores(
        plan.cases, rows, judgments, tolerance=plan.tolerance, n_boot=plan.n_boot, samples=plan.samples
    )
    triage = None
    if plan.triage_fp and not stopped and isinstance(judge, Judge):
        try:
            triage = judge.triage_many(triage_items(plan.cases, rows, scores))
        except BudgetExceeded:
            stopped = True
    if budget is not None:
        plan.extra["spent_usd"] = budget.spent
    manifest = build_manifest(plan, judge, stopped)
    write_run(plan.run_dir, manifest, rows, judgments, scores, triage)
    return RunResult(manifest, scores, rows, judgments, stopped)


def summary_lines(scores: dict[str, Any]) -> list[str]:
    strict = scores["metrics"]["strict"]
    ops = scores["ops"]
    reviewer, judge = ops.get("reviewer_cost_usd") or 0.0, ops.get("judge_cost_usd") or 0.0
    return [
        f"samples scorable: {scores['scorable_samples']}/{scores['total_samples']}  status: {scores['status_counts']}",
        f"strict recall    {fmt_metric(strict['recall'])}  (n={strict['recall']['n']} bugs)",
        f"strict precision {fmt_metric(strict['precision'])}",
        f"strict f1        {fmt_metric(strict['f1'])}",
        f"recall_high      {fmt_metric(strict['recall_high'])}",
        f"clean false-alarm rate {fmt_metric(strict['clean_false_alarm_rate'])}",
        f"cost: reviewer ${reviewer:.4f} + judge ${judge:.4f} = ${reviewer + judge:.4f}",
    ]


# ---------------------------------------------------------------- CLI


def _usage(message: str) -> int:
    print(f"aireview eval: {message}", file=sys.stderr)
    return EXIT_USAGE


def make_judge(backend: str, mode: str, judge_model: str, store: CassetteStore, **client_kwargs: Any) -> JudgeLike:
    """The judge for a backend. In record mode an existing judge cassette is reused (`resume`): a
    byte-identical judge request always gets the verdict already recorded for it, so every run containing
    the pair replays the same verdict and judge cassettes are never overwritten."""
    if backend in SYNTHETIC_BACKENDS:
        return ExactMatchJudge()
    return Judge(make_client(mode, store=store, **(client_kwargs | {"resume": True})), model=judge_model)


def reusable_judgments(
    judge: JudgeLike, items: Sequence[JudgeItem], stored: Sequence[Judgment]
) -> tuple[list[Judgment], list[JudgeItem]]:
    """(stored judgments still valid for `items`, items to judge again).

    A stored verdict is reused only when its cassette key equals the key of the request rebuilt from the
    current labels and code: an edited bug description, line range or after/ file changes the key. The
    exact-match judge is free and keyless, so its pairs are always judged again.
    """
    build = getattr(judge, "build_request", None)
    by_pair = {(j.case_id, j.sample, j.finding_index, j.bug_id): j for j in stored if j.verdict is not None}
    kept: list[Judgment] = []
    todo: list[JudgeItem] = []
    for item in items:
        j = by_pair.get((item.case.id, item.sample, item.finding_index, item.bug.id))
        if j is not None and build is not None and j.cassette_key == build(item)[0].key():
            kept.append(j)
        else:
            todo.append(item)
    return kept, todo


def estimate_line(estimate: dict[str, Any], budget_usd: float) -> str:
    discount = " (batch -50%)" if estimate["batch"] else ""
    reviewer_discount = " (batch -50%)" if estimate["reviewer_batch"] else ""
    return (
        f"estimate: {estimate['reviews']} reviews ~{estimate['reviewer_input_tokens']} in / "
        f"{estimate['reviewer_output_tokens']} out tokens = ${estimate['reviewer_usd']:.2f}{reviewer_discount}; "
        f"judge ~{estimate['judge_pairs']} pairs = ${estimate['judge_usd']:.2f}{discount}; "
        f"total ~${estimate['total_usd']:.2f} (budget ${budget_usd:.2f})"
    )


def cli_run(args: argparse.Namespace) -> int:
    try:
        config = load_config(Path(args.config))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return _usage(f"cannot load config {args.config}: {exc}")
    if config.backend not in KNOWN_BACKENDS:
        return _usage(f"unknown backend {config.backend!r}; expected one of {KNOWN_BACKENDS}")
    if config.backend in LLM_BACKENDS:
        config = resolve_config(config)
    if config.backend == "claude-cli" and args.mode == "replay":
        return _usage("the claude-cli backend is not cassette-backed; run it with --mode record")
    if not 0 <= args.tolerance <= MAX_JUDGE_TOL:
        return _usage(f"--tolerance must be within 0..{MAX_JUDGE_TOL} (the judged radius)")
    if args.samples < 1:
        return _usage("--samples must be >= 1")
    if args.sample_offset < 0:
        return _usage("--sample-offset must be >= 0")
    root = resolve_root(args.dataset)
    try:
        cases = select(load_dataset(root), args.split, args.case)
    except ValueError as exc:
        return _usage(str(exc))
    if not cases:
        return _usage(f"no cases in split {args.split!r} under {root}")

    run_id = args.run_id or default_run_id(config, args.split, args.samples, args.mode, now_utc())
    plan = RunPlan(
        run_id=run_id,
        run_dir=Path(args.runs_dir) / run_id,
        config=config,
        cases=cases,
        dataset_root=root,
        split=args.split,
        samples=args.samples,
        mode=args.mode,
        batch=args.batch,
        tolerance=args.tolerance,
        triage_fp=args.triage_fp,
        sample_offset=args.sample_offset,
        extra={"budget_usd": args.budget_usd, "cases_filter": args.case},
    )
    judge_model = args.judge_model or DEFAULT_JUDGE_MODEL
    store = CassetteStore()
    spends = args.mode == "record" and config.backend not in SYNTHETIC_BACKENDS
    if spends:
        requests = [job[4] for job in reviewer_requests(plan)] if config.backend in LLM_BACKENDS else []
        try:
            estimate = estimate_cost(
                requests,
                judge_model,
                args.batch,
                judged_reviews=len(cases) * args.samples,
                reviewer_batch=args.batch and config.backend == "anthropic",
            )
        except KeyError as exc:
            return _usage(f"{exc.args[0]} (checked before any spend)")
        plan.extra["estimate"] = estimate
        print(estimate_line(estimate, args.budget_usd))
        if estimate["total_usd"] > args.budget_usd:
            print("refusing to start: the estimate exceeds --budget-usd")
            return EXIT_FAILED
        if config.backend == "anthropic" and not args.resume:
            existing = sum(1 for r in requests if store.exists(r))
            if existing:
                return _usage(conflict_message(existing))
        if not args.yes and not confirm(f"Record {run_id}?"):
            print("aborted")
            return EXIT_FAILED

    budget = BudgetTracker(args.budget_usd) if spends else None
    client_kwargs = {"batch": args.batch, "resume": args.resume, "budget": budget}
    try:
        reviewer_client = (
            make_client(args.mode, store=store, **client_kwargs) if config.backend == "anthropic" else None
        )
        judge = make_judge(config.backend, args.mode, judge_model, store, **client_kwargs)
    except RuntimeError as exc:
        return _usage(str(exc))
    print(f"run {run_id}: {config.name} on {len(cases)} cases x k={args.samples} ({args.mode})")
    try:
        result = execute(plan, reviewer_client, judge, budget, chunk_size=None if args.batch else CHUNK_SIZE)
    except CassetteConflict as exc:
        return _usage(str(exc))
    print("\n".join(summary_lines(result.scores)))
    print(f"wrote {plan.run_dir}")
    if args.mlflow:
        from aireview.evals.sinks import log_run

        log_run(plan.run_dir)
    if result.incomplete:
        print(f"INCOMPLETE: budget ${args.budget_usd:.2f} exhausted (spent ${budget.spent if budget else 0:.4f})")
        return EXIT_FAILED
    return EXIT_OK


def cli_score(args: argparse.Namespace) -> int:
    """Re-score a run dir from its reviews; judge only the pairs without a usable judgment."""
    run_dir = Path(args.run_dir)
    try:
        manifest = RunManifest.model_validate(read_json(run_dir / "manifest.json"))
    except (OSError, ValueError) as exc:
        return _usage(f"cannot read {run_dir / 'manifest.json'}: {exc}")
    tol = manifest.tolerance if args.tolerance is None else args.tolerance
    if not 0 <= tol <= MAX_JUDGE_TOL:
        return _usage(f"--tolerance must be within 0..{MAX_JUDGE_TOL}")
    root = resolve_root(manifest.extra.get("dataset", "evals/dataset"))
    try:
        cases = select(load_dataset(root), None, manifest.case_ids)
    except ValueError as exc:
        return _usage(str(exc))
    current_hash = dataset_hash(root)
    if current_hash != manifest.dataset_hash:
        print(
            f"warning: dataset changed since the run ({manifest.dataset_hash[:12]} -> {current_hash[:12]}); rescoring with current labels"
        )
        manifest.extra.setdefault("original_dataset_hash", manifest.dataset_hash)
        manifest.dataset_hash = current_hash

    rows = load_reviews(run_dir)
    judge_model = manifest.judge_model or DEFAULT_JUDGE_MODEL
    mode = getattr(args, "mode", "replay")
    triage_fp = bool(getattr(args, "triage_fp", False))
    budget_usd = float(getattr(args, "budget_usd", DEFAULT_SCORE_BUDGET_USD))
    spends = mode == "record" and manifest.config.backend not in SYNTHETIC_BACKENDS
    budget = BudgetTracker(budget_usd) if spends else None
    try:
        judge = make_judge(manifest.config.backend, mode, judge_model, CassetteStore(), budget=budget)
    except RuntimeError as exc:  # record mode without ANTHROPIC_API_KEY
        return _usage(str(exc))
    kept, todo = reusable_judgments(judge, judge_items(cases, rows), load_judgments(run_dir))
    stored_triage = read_jsonl(run_dir / "triage.jsonl")
    if spends:
        triage_bound = triage_upper_bound(rows, stored_triage) if triage_fp else 0
        try:
            estimate = score_estimate(judge_model, len(todo), triage_bound)
        except KeyError as exc:
            return _usage(f"{exc.args[0]} (checked before any spend)")
        manifest.extra["score_estimate"] = estimate
        print(
            f"estimate: judge {estimate['judge_pairs']} pairs + triage <= {estimate['triage_items']} findings "
            f"= ${estimate['total_usd']:.2f} (budget ${budget_usd:.2f})"
        )
        if estimate["total_usd"] > budget_usd:
            print("refusing to start: the estimate exceeds --budget-usd")
            return EXIT_FAILED
        if (
            (todo or triage_bound)
            and not getattr(args, "yes", False)
            and not confirm(f"Record judge calls for {run_dir.name}?")
        ):
            print("aborted")
            return EXIT_FAILED

    new, stopped = run_judge(judge, todo)
    judgments = kept + new
    n_boot = int(manifest.extra.get("n_boot", 10000))
    scores = compute_scores(cases, rows, judgments, tolerance=tol, n_boot=n_boot, samples=manifest.samples)

    fp_items = triage_items(cases, rows, scores)
    n_triaged = 0
    if triage_fp and isinstance(judge, Judge) and not stopped:
        kept_triage, triage_todo = reusable_triage(judge, fp_items, stored_triage)
        try:
            fresh = judge.triage_many(triage_todo)
        except BudgetExceeded:
            fresh, stopped = [], True
        n_triaged = len(triage_todo)
        triage = sort_triage(kept_triage + fresh) or None
        manifest.extra["triage_prompt_version"] = TRIAGE_PROMPT_VERSION
    else:
        if triage_fp and not isinstance(judge, Judge):
            print("note: --triage-fp needs the LLM judge; synthetic runs are not triaged")
        current = {(item.case.id, item.sample, item.finding_index) for item in fp_items}
        triage = [t for t in stored_triage if (t["case_id"], t["sample"], t["finding_index"]) in current] or None

    manifest.tolerance = tol
    manifest.judge_model = judge.model
    manifest.judge_prompt_version = getattr(judge, "prompt_version", JUDGE_PROMPT_VERSION)
    manifest.extra["rescored_at"] = now_utc().isoformat(timespec="seconds")
    if budget is not None:
        manifest.extra["score_spent_usd"] = budget.spent
    if stopped:
        manifest.extra["incomplete"] = True
    write_run(run_dir, manifest, rows, judgments, scores, triage)
    print(f"re-judged {len(todo)} pairs ({sum(1 for j in new if j.verdict is None)} still failing); tolerance {tol}")
    if triage_fp:
        failing = sum(1 for t in triage or [] if t.get("label") is None)
        print(f"triaged {n_triaged} new false positives ({len(triage or [])} rows, {failing} without a label)")
    print("\n".join(summary_lines(scores)))
    if getattr(args, "mlflow", False):
        from aireview.evals.sinks import log_run

        log_run(run_dir)
    if stopped:
        print(f"INCOMPLETE: budget ${budget_usd:.2f} exhausted (spent ${budget.spent if budget else 0:.4f})")
        return EXIT_FAILED
    return EXIT_OK


def triage_upper_bound(rows: Sequence[ReviewRow], stored: Sequence[dict[str, Any]]) -> int:
    """Most triage calls a re-score can make: every finding of a scorable row without a labelled triage row."""
    labelled = {(t["case_id"], t["sample"], t["finding_index"]) for t in stored if t.get("label") is not None}
    return sum(
        1
        for r in rows
        if r.status == ReviewStatus.ok
        for i in range(len(r.findings))
        if (r.case_id, r.sample, i) not in labelled
    )


def score_estimate(judge_model: str, judge_pairs: int, triage_items: int) -> dict[str, Any]:
    """Judge-only cost estimate for `eval score --mode record` (same per-call constants as `estimate_cost`)."""
    per_call = cost_usd(judge_model, JUDGE_INPUT_TOKENS, JUDGE_OUTPUT_TOKENS)
    return {
        "judge_pairs": judge_pairs,
        "triage_items": triage_items,
        "judge_usd": judge_pairs * per_call,
        "triage_usd": triage_items * per_call,
        "total_usd": (judge_pairs + triage_items) * per_call,
    }


def reusable_triage(
    judge: Judge, items: Sequence[TriageItem], stored: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[TriageItem]]:
    """(stored triage rows still valid for `items`, items to triage again); like `reusable_judgments`, a row is
    reused only when it has a label and its cassette key equals the key of the request rebuilt now."""
    by_finding = {(t["case_id"], t["sample"], t["finding_index"]): t for t in stored if t.get("label") is not None}
    kept: list[dict[str, Any]] = []
    todo: list[TriageItem] = []
    for item in items:
        row = by_finding.get((item.case.id, item.sample, item.finding_index))
        if row is not None and row.get("cassette_key") == judge.build_triage_request(item).key():
            kept.append(row)
        else:
            todo.append(item)
    return kept, todo


def sort_triage(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda t: (t["case_id"], t["sample"], t["finding_index"]))
