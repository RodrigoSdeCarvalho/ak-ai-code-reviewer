"""Optional MLflow logging of a finished run dir. A no-op (with a warning) when mlflow is not installed."""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path
from typing import Any

from aireview.evals.report import load_run

EXPERIMENT = "aireview-eval"
HEADLINE = ("recall", "recall_high", "precision", "f1", "clean_false_alarm_rate", "pass_all_k")
OPS = ("cost_usd_per_review", "reviewer_cost_usd", "judge_cost_usd", "latency_p50_ms", "latency_p95_ms")
ARTEFACTS = ("scores.json", "report.md", "gate.json", "gate.md", "manifest.json")


def run_params(manifest: dict[str, Any], scores: dict[str, Any]) -> dict[str, Any]:
    config = manifest.get("config", {})
    return {
        "run_id": manifest.get("run_id"),
        "config": config.get("name"),
        "backend": config.get("backend"),
        "model": config.get("model"),
        "prompt_version": config.get("prompt_version"),
        "prompt_hash": manifest.get("prompt_hash"),
        "dataset_hash": manifest.get("dataset_hash"),
        "split": manifest.get("split"),
        "k": scores.get("samples"),
        "mode": manifest.get("mode"),
        "judge_model": manifest.get("judge_model"),
        "tolerance": manifest.get("tolerance"),
    }


def run_metrics(scores: dict[str, Any]) -> dict[str, float]:
    """Flat numeric metrics: `<mode>.<metric>` value and CI bounds, plus ops."""
    out: dict[str, float] = {}
    for mode in ("strict", "location"):
        for name in HEADLINE:
            m = scores["metrics"][mode].get(name) or {}
            for part in ("value", "ci_low", "ci_high"):
                if m.get(part) is not None:
                    key = f"{mode}.{name}" if part == "value" else f"{mode}.{name}.{part}"
                    out[key] = float(m[part])
    for name in OPS:
        value = scores.get("ops", {}).get(name)
        if value is not None:
            out[f"ops.{name}"] = float(value)
    out["scorable_samples"] = float(scores.get("scorable_samples", 0))
    return out


def log_run(run_dir: Path) -> bool:
    """Log params, metrics and artefacts of a run under experiment `aireview-eval`; False if mlflow is absent."""
    if importlib.util.find_spec("mlflow") is None:
        warnings.warn("mlflow is not installed (pip install -e '.[mlflow]'); skipping MLflow logging", stacklevel=2)
        return False
    import mlflow

    manifest, scores = load_run(run_dir)
    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=manifest.get("run_id")):
        mlflow.log_params({k: v for k, v in run_params(manifest, scores).items() if v is not None})
        mlflow.log_metrics(run_metrics(scores))
        for name in ARTEFACTS:
            if (run_dir / name).is_file():
                mlflow.log_artifact(str(run_dir / name))
    return True
