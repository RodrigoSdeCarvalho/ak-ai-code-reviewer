# aireview: a small AI code reviewer and the eval that gates it

`aireview` reviews a Python diff (or a whole repository) with one structured-output Claude call and writes its findings to a JSON file. The reviewer is deliberately modest. Most of this repository is the **eval**, which measures whether the reviewer works and can block a release when it gets worse:

- **A versioned golden set** of 56 Python cases in `evals/dataset/`:
  - 31 *seeded* cases: a realistic feature or refactor diff with a bug planted in it. Each bug is proven by a test that fails on the change and passes with the fix.
  - 15 *clean* cases: correct changes, used to measure false alarms.
  - 10 *real* cases: reverted fixes from recent public commits.
- **A grader.** Findings are matched to labelled bugs by location, then a separate LLM judge decides whether they describe the same defect. The judge is checked against human labels. A location-only score is always reported next to the strict one.
- **Statistics.** Every metric comes with a 95% cluster-bootstrap CI over cases. Runs are compared with a paired bootstrap and an exact McNemar test.
- **A gate.** `aireview eval gate` is a pure function of a run, a promoted baseline and three versioned config files. Its exit code is the release decision.
- **Offline reproducibility.** Every model call goes through content-addressed cassettes. `--mode replay` reproduces a run without an API key, and `--mode record` measures it again.

The eval report, with the measured numbers, is in [EVAL.md](EVAL.md).

## Quickstart

Python 3.12.

```bash
pip install -e '.[dev]'

# The full eval pipeline, offline and free. The oracle reviewer returns the gold bugs, so the
# scorer must report recall = precision = 1.0. Writes evals/runs/<run_id>/ (scores.json, report.md, ...).
aireview eval run --config evals/configs/oracle.yaml --split test --samples 1 --mode replay
```

Once the reference cassettes are committed, the same command with `--config evals/configs/v1-sonnet.yaml --samples 3` replays the headline run offline. *(Pending live runs.)*

## Running the reviewer

Each command below writes `findings.json` with `file`, `line` (post-change), `end_line`, `severity`, `category`, `title`, `description`, `suggestion`, `confidence`, plus `status` and token/cost `usage`. The exit code is 0 when `status` is `ok`, 2 for any other status (truncated, refused, schema or API error), and 3 for bad arguments.

```bash
export ANTHROPIC_API_KEY=...            # or put it in .env (see .env.example)

# A diff, with the post-change checkout for full-file context
aireview review --diff change.diff --repo path/to/repo --out findings.json

# A branch: the diff is computed with `git diff <base>`
aireview review --repo path/to/repo --base origin/main --out findings.json

# A whole repository: every tracked text file is treated as an addition
aireview review --repo path/to/repo --out findings.json

# Overrides: --config evals/configs/v1-haiku.yaml, --model, --prompt-version, --effort

# Non-LLM floor: ruff + bandit diagnostics on the changed lines only (no key needed)
aireview review --diff change.diff --repo path/to/repo --backend static --out findings.json
```

### As a Claude Code skill (headless)

[`skills/aireview-code-review/SKILL.md`](skills/aireview-code-review/SKILL.md) is the same reviewer packaged as a skill (named `aireview-code-review` because `code-review` is a built-in Claude Code skill). A unit test checks that its body matches `src/aireview/reviewer/prompts/v1.md` word for word, so the skill and the API reviewer cannot drift apart. To run it headlessly through Claude Code:

```bash
aireview review --diff change.diff --repo path/to/repo --backend claude-cli --out findings.json
```

That command runs `claude -p --bare --output-format json --json-schema <ReviewOutput schema> --model claude-sonnet-5-5 --no-session-persistence --max-budget-usd 1 --tools ""`. The prompt (the skill text followed by the diff context) goes in on stdin, because `--bare` does not load skills. All tools are disabled because the diff and the file contents are already in the prompt. The SKILL.md has the exact invocation. You can also use the skill interactively: copy `skills/aireview-code-review/` into `.claude/skills/` and ask Claude Code to review a diff (or run `/aireview-code-review`).

## Running the eval

```bash
# 1. Check the dataset: schema, diff regeneration, label placement, leakage grep, and that each case's
#    tests fail on the change and pass with the fix. --fast skips the tests.
aireview eval validate-dataset

# 2. Run a reviewer config over a split, k samples per case, then judge and score.
aireview eval run --config evals/configs/v1-sonnet.yaml --split test --samples 3 --mode replay

# 3. Read, compare, gate
aireview eval report  evals/runs/<run_id>
aireview eval compare evals/runs/<baseline_run> evals/runs/<candidate_run>
aireview eval gate --run evals/runs/<run_id>                  # exit 0 pass, 1 fail, 2 not comparable, 4 nothing gateable
aireview eval promote --run evals/runs/<run_id> --by <name> --reason "..."   # re-gates, writes evals/baseline.json

# 4. Judge calibration: label candidate pairs by hand (the judge verdict is hidden), then measure agreement
aireview eval label --run evals/runs/<run_id> --n 60 --rater <name>
aireview eval calibrate --cross-judge claude-opus-5-5
```

Model-free reference configs run the whole pipeline without an API key: `oracle` (the gold bugs; must score 1.0), `null` (no findings), `spam` (one finding per changed line) and `static` (ruff + bandit). Strict scores for `static` still need the LLM judge, so they replay only once the judge cassettes are recorded.

### Recording live runs

Record mode calls the Anthropic API and writes a cassette for every model outcome: successes and also truncated, refused, schema-error and wrong-model responses, so replay reproduces the same statuses and costs. Transport failures (API errors, timeouts) are not stored. Commit the cassettes, and `--mode replay` then reproduces the run.

```bash
export ANTHROPIC_API_KEY=...
aireview eval run --config evals/configs/v1-sonnet.yaml --split dev --samples 3 \
  --mode record --batch --budget-usd 5
```

- The runner prints its cost estimate (reviewer + judge, with the batch discount when `--batch` is set) before it starts and refuses to run above `--budget-usd` or with a model that has no price in `aireview.settings.PRICES`. It stops cleanly if measured spend reaches the budget; an incomplete run fails the gate.
- `--batch` uses the Message Batches API at 50% of the cost. Latency is then reported as not measured. A batch still running after 2 hours is cancelled, and the rows that finished are still charged and stored.
- Reviewer cassettes are write-once: record refuses to start if a cassette for one of its requests already exists, because overwriting it would change what an earlier run replays. `--resume` reuses cassettes recorded by an interrupted run. To record a config again independently (for example the noise-floor run), use `--sample-offset 3` (or 6, ...): its samples get their own cassettes, the offset is stored in the manifest, and the replay of that run takes the same flag.
- Judge cassettes are shared: a judge request identical to one already recorded reuses its verdict, so every run that contains the pair replays the same verdict.
- `aireview eval score <run_dir>` rescores a run (for example at another `--tolerance` or after a label fix). It reuses a stored judgment only when the judge request built from the current labels is identical, so an edited bug description is judged again.
- The `eval-live` GitHub workflow (manual dispatch) records a run with the `ANTHROPIC_API_KEY` secret, gates it, and uploads the run directory.

### CI

`.github/workflows/ci.yml` needs no secrets. It runs ruff, pytest (unit tests, the oracle/null/spam scorer checks, SKILL.md/prompt parity) and the fast dataset validator. It then replays every run listed in `evals/ci_runs.txt` (one `<config> <samples> [<sample offset>]` line per run) and gates it against `evals/baseline.json`. A missing cassette fails the job, because it means the prompt or config changed without a recorded run.

## Results

See [EVAL.md](EVAL.md). *Pending live runs:* no model run has been recorded yet, so the reviewer quality numbers, the noise floor, the gate thresholds and the judge calibration are all still to be measured. The thresholds in `evals/gate/` are marked as placeholders and cannot block until they are measured and accepted.

## Repository map

```
src/aireview/
  cli.py                    aireview review | eval ...
  models.py                 Finding, Review, Usage (the findings JSON contract)
  diffs.py                  unified-diff parsing, changed lines, repo -> diff
  llm/                      Anthropic client, cassettes (replay/record), Message Batches, budget
  reviewer/                 prompts/v1.md, context builder, reviewer, claude -p backend, static baseline
  evals/                    dataset + validator, runner, matching, judge, metrics, stats, report, gate,
                            calibration, MLflow sink
skills/aireview-code-review/ the reviewer as a Claude Code skill
evals/
  dataset/                  manifest.yaml + cases/<id>/ (case.yaml, before/, after/, change.diff, fixed/, tests/)
  configs/                  reviewer configs (v1-sonnet, v1-haiku, v1-opus, static, claude-cli, oracle, null, spam)
  gate/                     thresholds.yaml, tolerances.yaml, policy.yaml
  cassettes/                recorded model responses (reviewer/ and judge/)
  runs/                     committed runs cited by EVAL.md
  judge_calibration/        human labels for the judge
tests/                      unit tests (no network)
```

`evals/dataset/AUTHORING.md` explains how cases are written and validated.

## License

MIT, see [LICENSE](LICENSE).
