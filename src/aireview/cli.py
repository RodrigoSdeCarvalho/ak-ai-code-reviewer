"""Command line: `aireview review ...` runs the reviewer; `aireview eval ...` runs the eval.

Each sub-command delegates to a `cli_<name>(args) -> int` function in its module, imported lazily so
that `aireview review` does not pay for numpy/scipy imports.
"""

from __future__ import annotations

import argparse
import importlib
import sys

from aireview.settings import load_dotenv

COMMANDS: dict[str, str] = {
    "review": "aireview.reviewer.reviewer:cli_review",
    "eval.validate-dataset": "aireview.evals.validate:cli_validate",
    "eval.split": "aireview.evals.dataset:cli_split",
    "eval.run": "aireview.evals.runner:cli_run",
    "eval.score": "aireview.evals.runner:cli_score",
    "eval.report": "aireview.evals.report:cli_report",
    "eval.compare": "aireview.evals.report:cli_compare",
    "eval.gate": "aireview.evals.gate:cli_gate",
    "eval.promote": "aireview.evals.gate:cli_promote",
    "eval.label": "aireview.evals.calibration:cli_label",
    "eval.calibrate": "aireview.evals.calibration:cli_calibrate",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aireview", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="Review a diff or a repository and write findings JSON.")
    review.add_argument("--diff", help="Unified diff file (git diff format).")
    review.add_argument("--repo", help="Post-change repository path (adds full file content; or reviewed whole).")
    review.add_argument("--base", help="With --repo: git ref to diff against.")
    review.add_argument("--out", default="findings.json", help="Output JSON path (default: findings.json).")
    review.add_argument("--config", help="Reviewer config YAML (default: evals/configs/v1-sonnet.yaml values).")
    review.add_argument("--backend", choices=["anthropic", "claude-cli", "static"], help="Override the config backend.")
    review.add_argument("--model", help="Override the config model.")
    review.add_argument("--prompt-version", help="Override the config prompt version.")
    review.add_argument("--effort", help="Override output_config.effort.")

    ev = sub.add_parser("eval", help="Eval commands.").add_subparsers(dest="eval_command", required=True)

    p = ev.add_parser("validate-dataset", help="Validate every case (schema, diff, labels, tests, leakage).")
    p.add_argument("--dataset", default="evals/dataset")
    p.add_argument("--case", action="append", help="Only these case ids.")
    p.add_argument("--fast", action="store_true", help="Skip running the case tests.")
    p.add_argument("--write", action="store_true", help="Regenerate change.diff and size_bucket before validating.")

    p = ev.add_parser("split", help="Assign dev/test splits (stratified, fixed seed) and refresh the manifest.")
    p.add_argument("--dataset", default="evals/dataset")
    p.add_argument("--dev-fraction", type=float, default=0.4)
    p.add_argument("--seed", type=int, default=20261023)
    p.add_argument("--force", action="store_true", help="Re-assign splits that are already set.")

    p = ev.add_parser("run", help="Run a reviewer config over a split x k samples, then judge and score.")
    p.add_argument("--config", required=True)
    p.add_argument("--dataset", default="evals/dataset")
    p.add_argument("--split", choices=["dev", "test", "all"], default="test")
    p.add_argument("--case", action="append", help="Only these case ids.")
    p.add_argument("--samples", type=int, default=3)
    p.add_argument(
        "--sample-offset",
        type=int,
        default=0,
        help="First reviewer sample index (cassette key). Use k, 2k, ... for independent re-records of a config.",
    )
    p.add_argument("--mode", choices=["replay", "record"], default="replay")
    p.add_argument(
        "--resume",
        action="store_true",
        help="Record mode: reuse reviewer cassettes that already exist (otherwise record refuses to overwrite them).",
    )
    p.add_argument("--batch", action="store_true", help="Record mode: use the Message Batches API (50%% cost).")
    p.add_argument("--budget-usd", type=float, default=5.0)
    p.add_argument("--judge-model", default=None)
    p.add_argument("--tolerance", type=int, default=3)
    p.add_argument("--triage-fp", action="store_true", help="Judge unmatched findings (advisory).")
    p.add_argument("--run-id", default=None)
    p.add_argument("--runs-dir", default="evals/runs")
    p.add_argument("--mlflow", action="store_true", help="Also log the finished run to MLflow.")
    p.add_argument("--yes", action="store_true", help="Do not ask before spending (record mode).")

    p = ev.add_parser(
        "score", help="Re-score an existing run dir: judge (and triage) only what is missing, no reviewer calls."
    )
    p.add_argument("run_dir")
    p.add_argument("--tolerance", type=int, default=None)
    p.add_argument(
        "--mode",
        choices=["replay", "record"],
        default="replay",
        help="Judge mode for missing judgments and triage rows. Record needs ANTHROPIC_API_KEY and reuses "
        "existing judge cassettes (judge cassettes are always resumed, never overwritten).",
    )
    p.add_argument("--triage-fp", action="store_true", help="Also triage strict false positives (advisory).")
    p.add_argument("--budget-usd", type=float, default=2.0, help="Record mode: cap on judge + triage spend.")
    p.add_argument("--yes", action="store_true", help="Do not ask before spending (record mode).")
    p.add_argument("--mlflow", action="store_true", help="Also log the re-scored run to MLflow.")

    p = ev.add_parser("report", help="Render report.md for a run.")
    p.add_argument("run_dir")

    p = ev.add_parser("compare", help="Paired comparison of two runs on the same cases.")
    p.add_argument("baseline_run")
    p.add_argument("candidate_run")
    p.add_argument("--out", default=None)

    p = ev.add_parser("gate", help="Gate a run against the baseline; exit code is the decision.")
    p.add_argument("--run", required=True)
    p.add_argument("--baseline", default="evals/baseline.json")
    p.add_argument("--gate-dir", default="evals/gate")

    p = ev.add_parser("promote", help="Make a run the new baseline.")
    p.add_argument("--run", required=True)
    p.add_argument("--by", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--baseline", default="evals/baseline.json")
    p.add_argument("--gate-dir", default="evals/gate")
    p.add_argument("--accept-regression", action="store_true")

    p = ev.add_parser("label", help="Label judge candidate pairs by hand (judge verdict hidden).")
    p.add_argument("--run", action="append", required=True)
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--rater", required=True)
    p.add_argument("--labels", default="evals/judge_calibration/labels.jsonl")
    p.add_argument("--seed", type=int, default=7)

    p = ev.add_parser("calibrate", help="Judge-human agreement (TPR/TNR/kappa, error direction).")
    p.add_argument("--labels", default="evals/judge_calibration/labels.jsonl")
    p.add_argument("--cross-judge", default=None, help="Second judge model to compare on the labelled pairs.")
    p.add_argument("--mode", choices=["replay", "record"], default="replay")
    p.add_argument("--out", default="evals/judge_calibration/calibration.json")

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = _build_parser().parse_args(argv)
    name = args.command if args.command != "eval" else f"eval.{args.eval_command}"
    module_name, func_name = COMMANDS[name].split(":")
    func = getattr(importlib.import_module(module_name), func_name)
    return int(func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
