# EVAL: does the reviewer find real defects without crying wolf?

**Question.** For a diff, does the reviewer report the defects the change introduces (recall), are its reports right (precision), and does it stay quiet on correct changes (false alarms)? And is a candidate release *worse* than the current one in a way that should block the merge?

**Answer, in one line.** The shipped reviewer (v2: Sonnet 5.5, prompt v1, findings below 0.5 self-reported confidence dropped) finds **86% [76, 95]** of labelled defects on the held-out test split, at **88% [81, 95]** precision, with **0** high-severity false alarms on correct changes. That is enough to gate on, but recall is measured on mostly synthetic bugs, and the precision figure partly reflects silenced valid comments. Details below.

## What I measured

| Piece | Choice | Why |
|---|---|---|
| Dataset | 72 Python cases. 47 **seeded** bugs in fresh code, each proven by a test that fails on the PR and passes with the fix. 15 **clean** PRs (several decoys). 10 **real** bugs: reverted 2026-07+ fixes from public repos. | Seeded bugs are contamination-free and mechanically verified. Clean PRs measure false alarms. Real bugs check how far the seeded numbers transfer. |
| Split | dev 29 / test 43, drawn once with a fixed seed | I iterate on dev only. Every headline number below is from **test**. |
| Matching | Same file, and lines within ±3 of the label (or of a listed second legitimate location). Then an LLM judge (Haiku 5.5) decides "same defect?". Then a one-to-one Hungarian assignment. | Location alone over-credits a nit on the right line; text similarity under-credits paraphrases. A judge-free "location-only" score is always reported next to it. |
| Repeats | k = 3 samples per case | `temperature` can no longer be pinned, so variance is measured instead. |
| Statistics | 95% cluster-bootstrap CIs over cases; version comparisons paired on the same cases; exact McNemar on per-bug detection | Findings within a case are correlated, and paired designs detect smaller changes. |
| Gate | A pure function of (run, baseline, thresholds, tolerances, policy) with exit codes. Blocks on: an incomplete run; headline metrics not shown non-inferior within the measured noise floor; a demonstrated regression in any slice; 2+ newly missed critical/high bugs. | It runs in CI on every reviewer PR (`release-gate.yml`) and posts its decision on the PR. CI also replays the committed run on every push, with no key. |

## What I found (test split, 43 cases, 42 bugs, k = 3, strict scoring)

| Reviewer | Recall | Precision | Clean false alarms | pass^3 | $ / review | Gate vs baseline |
|---|---|---|---|---|---|---|
| static analysis (ruff + bandit) | 0.02 | 0.07 | 0.00 | — | 0 | — |
| v1: Sonnet 5.5, prompt v1 | 0.86 [0.76, 0.95] | 0.56 [0.47, 0.67] | 0.00 | 0.83 | 0.014 | baseline |
| **v2: v1 + confidence ≥ 0.5** | **0.86 [0.76, 0.95]** | **0.88 [0.81, 0.95]** | 0.00 | 0.83 | 0.014 | **PASS** (PR #1) |
| Haiku 5.5, prompt v1 | 0.81 [0.69, 0.92] | 0.63 [0.51, 0.75] | 0.00 | 0.79 | 0.0006 | **FAIL** (PR #2) |

**1. The change I made, and what happened.** On dev, v1's false positives were almost all medium/low comments with low self-reported confidence: median 0.30, against 0.93 for true positives. I registered a hypothesis before touching test: a 0.5 threshold raises precision by at least 10 pp and costs at most 3 pp of recall. v2 sends the identical model request, so it replays v1's samples, and the comparison is paired sample by sample. **Precision rose by +0.32 [0.23, 0.41] and recall moved by exactly 0.** The prediction that real and medium bugs would lose recall was wrong.

The catch: an advisory triage of what v2 removed says 13 of the 70 dropped "false positives" were *valid issues the dataset doesn't label*. v1 made 24 such comments on test, and v2 silences 13 of them. Precision against complete labels would rise less. Some useful feedback is the price.

**2. My first gate was wrong, and an A/A run showed it.** Haiku is 25× cheaper per review. Against Sonnet, every average said "no detectable change": recall −0.05 [−0.16, +0.06], precision +0.06 [−0.05, +0.18]. The first gate still failed it, because one high-severity bug that Sonnet found 3/3 was missed by Haiku 3/3. That looked like the gate doing its job.

Then I recorded the *unchanged* v1 config a second time to measure the noise floor. This A/A run **failed its own gate**: a high-severity bug went from 3/3 to 0/3 by chance alone. So the Haiku verdict had been noise.

The A/A run also showed the opposite hole. The regression rule only fired on a *demonstrated* drop, so it would have passed a candidate whose recall CI still allows a 20-point loss. I recalibrated from the A/A measurement (see `evals/gate/tolerances.yaml` for the provenance of each value):
- tolerances = the A/A CI bounds: recall 0.10, recall_high 0.15, precision 0.07;
- headline metrics must show **non-inferiority**: the bad end of the paired CI must stay within tolerance;
- the per-bug rule now tolerates one flip.

Under the recalibrated gate:
- **A/A: PASS.**
- **v2: PASS** (PR #1, merged).
- **Haiku: FAIL** (PR #2). The verdict now comes on evidence: its recall CI reaches −0.16, past the noise floor. It may well be fine, but 42 bugs cannot show that. Proving a 25× cheaper model is not worse needs a bigger set, not a better gate.

**3. The eval was wrong once, and the error analysis caught it.** Reading every dev miss, I found the reviewer naming a quadratic page walk in all 3 samples, but at the callee, while the label pointed at the calling loop. That was scored as a miss plus a false positive. I added second legitimate locations to the label schema and audited all 72 cases *without looking at model outputs* (8 bugs gained one). Dev recall went from 0.86 to 0.92. The same process caught a run judged with an old rubric: the gate returned `NOT_COMPARABLE` instead of a verdict.

**Where it fails:**
- Defects that need code the reviewer is never shown: recall 0.50 on the 4 such test bugs (`unshown_context` tag), against 0.89 on the rest.
- Severity agreement is 59% exact (100% within one level).
- Large diffs have lower precision (0.46 on L, 0.79 on S, for v1).

## Where I would not trust this

- **Synthetic bugs, same model family.** Claude agents wrote the seeded and clean cases, and Claude models do the reviewing. A shared "style" may make bugs easier to spot than human-written ones. A 2026 study reports synthetic bugs scoring far higher than real ones (arXiv 2606.15689). Our 7 real bugs score close to the seeded ones (recall 0.81 vs 0.87), but they are reversed fixes ("a PR that deletes the guard"), which are easier than organic bugs, and n = 7.
- **The judge's validation is weaker than it looks.** On 60 stratified pairs, the Haiku judge agreed 100% (κ = 1.0) with an **agent rater** (Claude Opus, blind to the verdicts, acting as the human; disclosed, and agreed with the recruiter). Same family, and a fairly easy sample. Read it as an upper bound, not a judge–human agreement. An Opus cross-judge disagreed on 3/60 pairs, all in the lenient direction. The judge-free location-only score (recall 0.87 for v2) shows how little the headline depends on the judge here.
- **Small n.** CIs are ±10–15 pp. The clean false-alarm rate rests on 8 clean test cases. Slices under 6 bugs are marked `INSUFFICIENT_DATA` and cannot fail the gate (security and performance sit at exactly 6).
- **Precision counts only labelled bugs.** Valid but unlabelled comments count as false positives. `precision_high` (findings rated high or critical: 0.96 for v1) and the triage are the correction, and both are advisory.
- **One A/A pair.** The tolerances rest on a single A/A comparison (recall −0.016 [−0.081, +0.028], precision +0.007 [−0.058, +0.066]). One measurement of the noise is not a distribution of it. With k = 3, individual bugs flip between runs; pass^3 is 0.83.
- **Python only; one call per review; no repository exploration.**

## Reproduce

```bash
pip install -e ".[dev]"
aireview eval run --config evals/configs/v2-sonnet.yaml --split test --samples 3 --mode replay   # every number above, offline, no key
aireview eval gate --run evals/runs/<run-id>                                                    # exit code = release decision
aireview eval run --config evals/configs/v2-sonnet.yaml --split test --samples 3 --sample-offset 6 --mode record  # re-measure (needs ANTHROPIC_API_KEY, ~$2)
```

Each run directory in `evals/runs/` holds `manifest.json` (git sha, dataset/prompt/config hashes), `reviews.jsonl`, `judgments.jsonl`, `scores.json`, `report.md` and, where gated, `gate.md`. Total live spend for everything above: about $4.
