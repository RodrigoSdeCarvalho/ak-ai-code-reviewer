"""Judge calibration: blind human labels of judged pairs, then judge-human agreement (and a cross-judge).

`label` samples judged (finding, bug) pairs stratified by judge verdict and line distance, shows them
without the verdict, and appends the rater's label to labels.jsonl. `calibrate` joins labels with the
judge verdicts: raw agreement, Cohen's kappa (3-class and same-vs-not), TPR/TNR and the direction of
the errors (lenient = judge says same where the human says different: the dangerous one for a gate).
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aireview.evals.dataset import load_dataset, resolve_root, select
from aireview.evals.judge import CONTEXT_LINES, Judge, JudgeItem, code_context
from aireview.evals.matching import finding_span, line_distance
from aireview.evals.report import load_judgments, load_reviews, md_table, read_json, read_jsonl, write_json
from aireview.evals.schema import Bug, Case
from aireview.evals.stats import wilson_ci
from aireview.llm.cassette import CassetteStore, make_client
from aireview.models import Finding

VERDICT_SHARES = {"same": 0.4, "different": 0.4, "unsure": 0.2}
DISTANCE_BUCKETS = ((0, 0), (1, 3), (4, 10_000))
KEYS = {"s": "same", "d": "different", "u": "unsure"}
TARGET_KAPPA = 0.7
LABELS = ("same", "different", "unsure")


@dataclass
class Pair:
    """One judged candidate pair, with what the rater needs to see (never the verdict)."""

    pair_id: str
    run_id: str
    run_dir: Path
    case: Case
    case_dir: Path
    sample: int
    finding_index: int
    finding: Finding
    bug: Bug
    verdict: str | None
    distance: int


# ---------------------------------------------------------------- loading


def resolve_run(ref: str, runs_dir: Path = Path("evals/runs")) -> Path:
    """A run dir path, or a run id under evals/runs."""
    path = Path(ref)
    return path if (path / "manifest.json").is_file() else resolve_root(runs_dir) / ref


def run_pairs(run_dir: Path) -> list[Pair]:
    """Every judged pair of a run with a verdict (judge errors are not calibration material)."""
    manifest = read_json(run_dir / "manifest.json")
    root = resolve_root(manifest.get("extra", {}).get("dataset", "evals/dataset"))
    cases = {c.id: (c, d) for c, d in select(load_dataset(root), None, manifest["case_ids"])}
    rows = {(r.case_id, r.sample): r for r in load_reviews(run_dir)}
    out = []
    for j in load_judgments(run_dir):
        row = rows.get((j.case_id, j.sample))
        if j.verdict is None or row is None or j.case_id not in cases or j.finding_index >= len(row.findings):
            continue
        case, case_dir = cases[j.case_id]
        bug = next((b for b in case.bugs if b.id == j.bug_id), None)
        if bug is None:
            continue
        finding = row.findings[j.finding_index]
        out.append(
            Pair(
                pair_id=j.cassette_key or f"{manifest['run_id']}:{j.case_id}:{j.sample}:{j.finding_index}:{j.bug_id}",
                run_id=manifest["run_id"],
                run_dir=run_dir,
                case=case,
                case_dir=case_dir,
                sample=j.sample,
                finding_index=j.finding_index,
                finding=finding,
                bug=bug,
                verdict=j.verdict.value,
                distance=line_distance(finding, bug),
            )
        )
    return out


# ---------------------------------------------------------------- sampling


def allocate(n: int, available: dict[str, int], shares: dict[str, float] = VERDICT_SHARES) -> dict[str, int]:
    """Per-verdict quota close to `shares`, capped by availability; shortfalls go to verdicts with spare pairs."""
    quota = {v: min(available.get(v, 0), int(n * s)) for v, s in shares.items()}
    remaining = min(n, sum(available.values())) - sum(quota.values())
    while remaining > 0:
        spare = [v for v in shares if quota[v] < available.get(v, 0)]
        if not spare:
            break
        for v in sorted(spare, key=lambda v: -shares[v]):
            if remaining == 0:
                break
            quota[v] += 1
            remaining -= 1
    return quota


def _bucket(distance: int) -> int:
    return next(i for i, (lo, hi) in enumerate(DISTANCE_BUCKETS) if lo <= distance <= hi)


def sample_pairs(pairs: Iterable[Pair], n: int, seed: int, exclude: set[str] | None = None) -> list[Pair]:
    """Stratified sample: verdict quotas (~40/40/20), round-robin over line-distance buckets, shuffled output."""
    rng = random.Random(seed)
    exclude = exclude or set()
    unique: dict[str, Pair] = {}
    for p in pairs:
        if p.pair_id not in exclude:
            unique.setdefault(p.pair_id, p)
    by_verdict: dict[str, list[Pair]] = {}
    for p in sorted(unique.values(), key=lambda p: p.pair_id):
        by_verdict.setdefault(p.verdict or "unsure", []).append(p)
    quota = allocate(n, {v: len(ps) for v, ps in by_verdict.items()})
    chosen: list[Pair] = []
    for verdict, k in quota.items():
        buckets: dict[int, list[Pair]] = {}
        for p in by_verdict.get(verdict, []):
            buckets.setdefault(_bucket(p.distance), []).append(p)
        for items in buckets.values():
            rng.shuffle(items)
        order = sorted(buckets)
        while k > 0 and any(buckets[b] for b in order):
            for b in order:
                if k > 0 and buckets[b]:
                    chosen.append(buckets[b].pop())
                    k -= 1
    rng.shuffle(chosen)
    return chosen


# ---------------------------------------------------------------- labelling


def render_pair(pair: Pair) -> str:
    """What the rater sees: code around both, the labelled defect and the finding. Never the verdict."""
    start, end = finding_span(pair.finding)
    code = code_context(
        pair.case_dir,
        [(pair.bug.file, pair.bug.line_start, pair.bug.line_end), (pair.finding.file, start, end)],
        CONTEXT_LINES,
    )
    return (
        f"{code}\n\n"
        f"LABELLED DEFECT ({pair.bug.file}:{pair.bug.line_start}-{pair.bug.line_end})\n{pair.bug.description.strip()}\n\n"
        f"REVIEW FINDING ({pair.finding.file}:{start}-{end})\n{pair.finding.title.strip()}\n"
        f"{pair.finding.description.strip()}\n"
    )


def label_row(pair: Pair, label: str, rater: str) -> dict[str, Any]:
    return {
        "pair_id": pair.pair_id,
        "run_id": pair.run_id,
        "run_dir": pair.run_dir.as_posix(),
        "case_id": pair.case.id,
        "sample": pair.sample,
        "finding_index": pair.finding_index,
        "bug_id": pair.bug.id,
        "label": label,
        "rater": rater,
        "labelled_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def label_pairs(
    pairs: Sequence[Pair],
    rater: str,
    labels_path: Path,
    read: Callable[[str], str] = input,
    write: Callable[[str], None] = print,
) -> int:
    """Ask for s/d/u per pair (q quits); append each label at once. Returns the number labelled."""
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    for i, pair in enumerate(pairs, start=1):
        write(f"\n=== pair {i}/{len(pairs)} ({pair.case.id}) ===\n{render_pair(pair)}")
        while True:
            try:
                answer = read("Same defect? [s]ame / [d]ifferent / [u]nsure / [q]uit: ").strip().lower()[:1]
            except EOFError:
                answer = "q"
            if answer in KEYS or answer == "q":
                break
        if answer == "q":
            break
        with labels_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(label_row(pair, KEYS[answer], rater), ensure_ascii=False) + "\n")
        done += 1
    return done


def cli_label(args: argparse.Namespace) -> int:
    labels_path = resolve_root(Path(args.labels).parent) / Path(args.labels).name
    pairs = [p for ref in args.run for p in run_pairs(resolve_run(ref))]
    exclude = {r["pair_id"] for r in read_jsonl(labels_path) if r.get("rater") == args.rater}
    chosen = sample_pairs(pairs, args.n, args.seed, exclude)
    if not chosen:
        print("nothing to label: no judged pairs left for this rater")
        return 0
    n = label_pairs(chosen, args.rater, labels_path)
    print(f"labelled {n} pairs -> {labels_path}")
    return 0


# ---------------------------------------------------------------- agreement


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> float | None:
    """Cohen's kappa of two label sequences; None when undefined (no items, or chance agreement is 1)."""
    if not a or len(a) != len(b):
        return None
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / n**2
    if expected >= 1:
        return None
    return (observed - expected) / (1 - expected)


def binary(label: str) -> str:
    """Same vs not-same (unsure counts as not-same: it never matches in strict scoring)."""
    return "same" if label == "same" else "not_same"


def agreement(pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """(human, judge) label pairs -> agreement statistics. TPR/TNR exclude pairs the human marked unsure."""
    human = [h for h, _ in pairs]
    judge = [j for _, j in pairs]
    n = len(pairs)
    pos = [(h, j) for h, j in pairs if h == "same"]
    neg = [(h, j) for h, j in pairs if h == "different"]
    tp = sum(1 for _, j in pos if j == "same")
    tn = sum(1 for _, j in neg if j != "same")
    confusion = {h: {j: sum(1 for x, y in pairs if x == h and y == j) for j in LABELS} for h in LABELS}
    return {
        "n": n,
        "raw_agreement": sum(h == j for h, j in pairs) / n if n else None,
        "kappa_3class": cohen_kappa(human, judge),
        "kappa_binary": cohen_kappa([binary(h) for h in human], [binary(j) for j in judge]),
        "tpr": tp / len(pos) if pos else None,
        "tpr_ci": list(wilson_ci(tp, len(pos))) if pos else None,
        "tnr": tn / len(neg) if neg else None,
        "tnr_ci": list(wilson_ci(tn, len(neg))) if neg else None,
        "lenient_errors": sum(1 for _, j in neg if j == "same"),
        "harsh_errors": sum(1 for _, j in pos if j == "different"),
        "confusion": confusion,  # rows: human label, columns: judge verdict
    }


def _verdicts(run_dir: Path) -> dict[tuple[str, int, int, str], str | None]:
    return {
        (j.case_id, j.sample, j.finding_index, j.bug_id): j.verdict.value if j.verdict else None
        for j in load_judgments(run_dir)
    }


def join_labels(labels: Sequence[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    """(label row, primary judge verdict) for every label whose pair still has a verdict."""
    cache: dict[str, dict] = {}
    out = []
    for row in labels:
        run_dir = resolve_run(row.get("run_dir") or row["run_id"])
        key = run_dir.as_posix()
        if key not in cache:
            cache[key] = _verdicts(run_dir) if (run_dir / "judgments.jsonl").is_file() else {}
        verdict = cache[key].get((row["case_id"], row["sample"], row["finding_index"], row["bug_id"]))
        if verdict is not None:
            out.append((row, verdict))
    return out


def cross_judge_verdicts(
    labels: Sequence[dict[str, Any]], judge: Judge
) -> dict[tuple[str, str, int, int, str], str | None]:
    """Re-judge the labelled pairs with another judge (through the cassette layer)."""
    items: list[JudgeItem] = []
    keys = []
    pairs_by_run: dict[str, dict] = {}
    for row in labels:
        run_dir = resolve_run(row.get("run_dir") or row["run_id"])
        if run_dir.as_posix() not in pairs_by_run:
            pairs_by_run[run_dir.as_posix()] = {
                (p.case.id, p.sample, p.finding_index, p.bug.id): p for p in run_pairs(run_dir)
            }
        pair = pairs_by_run[run_dir.as_posix()].get(
            (row["case_id"], row["sample"], row["finding_index"], row["bug_id"])
        )
        if pair is not None:
            items.append(JudgeItem(pair.case, pair.case_dir, pair.sample, pair.finding_index, pair.finding, pair.bug))
            keys.append((row["run_id"], row["case_id"], row["sample"], row["finding_index"], row["bug_id"]))
    judgments = judge.judge_many(items)
    return {k: (j.verdict.value if j.verdict else None) for k, j in zip(keys, judgments, strict=True)}


def _row_key(row: dict[str, Any]) -> tuple[str, str, int, int, str]:
    return (row["run_id"], row["case_id"], row["sample"], row["finding_index"], row["bug_id"])


def calibrate(
    labels: Sequence[dict[str, Any]], cross: dict[tuple[str, str, int, int, str], str | None] | None = None
) -> dict[str, Any]:
    """calibration.json content from label rows (and optional cross-judge verdicts keyed like the rows)."""
    joined = join_labels(labels)
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_labels": len(labels),
        "n_joined": len(joined),
        "raters": sorted({r["rater"] for r in labels}),
        "target_kappa": TARGET_KAPPA,
        "primary": agreement([(row["label"], verdict) for row, verdict in joined]),
        "cross_judge": None,
    }
    judge_models = set()
    for row, _ in joined:
        manifest_path = resolve_run(row.get("run_dir") or row["run_id"]) / "manifest.json"
        if manifest_path.is_file():
            judge_models.add(read_json(manifest_path).get("judge_model"))
    result["primary"]["judge_models"] = sorted(m for m in judge_models if m)
    kappa = result["primary"]["kappa_binary"]
    result["judge_metrics_advisory"] = kappa is None or kappa < TARGET_KAPPA
    if cross is not None:
        both = [(row, verdict, cross.get(_row_key(row))) for row, verdict in joined]
        both = [(row, v, c) for row, v, c in both if c is not None]
        result["cross_judge"] = {
            "vs_human": agreement([(row["label"], c) for row, _, c in both]),
            "kappa_vs_primary_3class": cohen_kappa([v for _, v, _ in both], [c for _, _, c in both]),
            "kappa_vs_primary_binary": cohen_kappa([binary(v) for _, v, _ in both], [binary(c) for _, _, c in both]),
            "n": len(both),
        }
    return result


def _fmt(x: Any) -> str:
    if x is None:
        return "n/a"
    if isinstance(x, list):
        return "[" + ", ".join(_fmt(v) for v in x) + "]"
    return f"{x:.3f}" if isinstance(x, float) else str(x)


def render_calibration(result: dict[str, Any]) -> str:
    primary = result["primary"]
    cross = (result.get("cross_judge") or {}).get("vs_human")
    names = (
        "n",
        "raw_agreement",
        "kappa_3class",
        "kappa_binary",
        "tpr",
        "tpr_ci",
        "tnr",
        "tnr_ci",
        "lenient_errors",
        "harsh_errors",
    )
    header = ["metric", f"primary ({', '.join(primary.get('judge_models', [])) or '?'})"]
    if cross:
        header.append(f"cross ({result.get('cross_judge_model')})")
    rows = [[name, _fmt(primary[name]), *([_fmt(cross[name])] if cross else [])] for name in names]
    lines = [
        f"# Judge calibration ({result['n_joined']} labelled pairs, raters: {', '.join(result['raters'])})",
        "",
        *md_table(header, rows),
        "",
        "Confusion (rows = human, columns = primary judge):",
        "",
        *md_table(["human \\ judge", *LABELS], [[h, *[primary["confusion"][h][j] for j in LABELS]] for h in LABELS]),
        "",
    ]
    if result.get("cross_judge"):
        c = result["cross_judge"]
        lines += [
            f"Cross-judge vs primary over {c['n']} pairs: kappa 3-class {_fmt(c['kappa_vs_primary_3class'])}, "
            f"binary {_fmt(c['kappa_vs_primary_binary'])}.",
            "",
        ]
    verdict = "ADVISORY (kappa below target)" if result["judge_metrics_advisory"] else "OK"
    lines.append(f"Target binary kappa >= {TARGET_KAPPA}: judge-dependent metrics are {verdict}.")
    return "\n".join(lines) + "\n"


def cli_calibrate(args: argparse.Namespace) -> int:
    labels_path = resolve_root(Path(args.labels).parent) / Path(args.labels).name
    labels = read_jsonl(labels_path)
    if not labels:
        print(f"no labels in {labels_path}; run `aireview eval label` first")
        return 3
    cross = None
    if args.cross_judge:
        # Judge cassettes are write-once: record reuses an existing verdict for an identical request.
        judge = Judge(make_client(args.mode, store=CassetteStore(), resume=True), model=args.cross_judge)
        cross = cross_judge_verdicts(labels, judge)
    result = calibrate(labels, cross)
    if args.cross_judge:
        result["cross_judge_model"] = args.cross_judge
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, result)
    print(render_calibration(result))
    print(f"wrote {out}")
    return 0
