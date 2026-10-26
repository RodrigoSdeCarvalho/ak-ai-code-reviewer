"""report.md rendering and the paired comparison between two runs."""

import argparse
import json
from pathlib import Path

import pytest

from aireview.evals.report import (
    NO_CHANGE,
    cli_compare,
    cli_report,
    comparability_problems,
    majority,
    render,
    verdict_label,
)
from test_runner import make_dataset, run_synthetic


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("report")
    dataset = make_dataset(root / "dataset")
    for backend in ("oracle", "null", "spam"):
        run_synthetic(dataset, root, backend)
    return root / "runs"


def test_report_sections(runs: Path):
    text = (runs / "oracle" / "report.md").read_text(encoding="utf-8")
    for heading in (
        "# Eval run `oracle`",
        "## Headline",
        "## Clean cases (false alarms)",
        "## Consistency over k samples",
        "## Severity / category agreement",
        "## Slices",
        "## Location tolerance sensitivity",
        "## Serving outcomes",
        "## Ops",
        "## Missed bugs",
        "## False positives (strict)",
    ):
        assert heading in text, heading
    assert "| recall | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 3 |" in text
    assert "INSUFFICIENT_DATA" in text  # 3 bugs < 6


def test_report_lists_misses_and_false_positives(runs: Path):
    null = (runs / "null" / "report.md").read_text(encoding="utf-8")
    assert "| seeded-calc | b1 | app/calc.py:8-8 | high | logic | 0.00 |" in null
    spam = (runs / "spam" / "report.md").read_text(encoding="utf-8")
    fp_section = spam.split("## False positives (strict)")[1]
    assert "Review this changed line" in fp_section


def test_render_without_reviews_and_cli_report(runs: Path):
    manifest = json.loads((runs / "null" / "manifest.json").read_text(encoding="utf-8"))
    scores = json.loads((runs / "null" / "scores.json").read_text(encoding="utf-8"))
    assert "(reviews.jsonl not available)" in render(scores, manifest)
    assert cli_report(argparse.Namespace(run_dir=str(runs / "null"))) == 0
    assert cli_report(argparse.Namespace(run_dir=str(runs / "missing"))) == 3


def test_cli_compare_oracle_vs_null(runs: Path, tmp_path: Path):
    out = tmp_path / "cmp"
    ns = argparse.Namespace(baseline_run=str(runs / "oracle"), candidate_run=str(runs / "null"), out=str(out))
    assert cli_compare(ns) == 0
    result = json.loads((out / "compare.json").read_text(encoding="utf-8"))
    assert result["metrics"]["recall"]["delta"] == -1.0
    assert result["metrics"]["recall"]["label"] == "regressed"
    assert result["mcnemar"]["lost"] == 3 and result["mcnemar"]["gained"] == 0
    assert {f["change"] for f in result["mcnemar"]["flips"]} == {"lost"}
    assert "kind:seeded" in result["slices"]
    assert "Exact McNemar" in (out / "compare.md").read_text(encoding="utf-8")


def test_cli_compare_refuses_incomparable_runs(runs: Path, tmp_path: Path):
    other = tmp_path / "other"
    other.mkdir()
    for name in ("scores.json", "reviews.jsonl"):
        (other / name).write_bytes((runs / "null" / name).read_bytes())
    manifest = json.loads((runs / "null" / "manifest.json").read_text(encoding="utf-8"))
    (other / "manifest.json").write_text(json.dumps(manifest | {"tolerance": 5}), encoding="utf-8")
    ns = argparse.Namespace(baseline_run=str(runs / "oracle"), candidate_run=str(other), out=None)
    assert cli_compare(ns) == 2


def test_comparability_and_labels():
    base = {"judge_model": "a", "judge_prompt_version": "v", "tolerance": 3, "case_ids": ["x", "y"]}
    assert comparability_problems(base, dict(base)) == []
    problems = comparability_problems(base, base | {"judge_model": "b", "case_ids": ["x"]})
    assert len(problems) == 2
    assert verdict_label("recall", {"delta": 0.02, "half_width": 0.05}) == NO_CHANGE
    assert verdict_label("recall", {"delta": 0.1, "half_width": 0.05}) == "improved"
    assert verdict_label("clean_false_alarm_rate", {"delta": 0.1, "half_width": 0.05}) == "regressed"
    assert verdict_label("precision", {"delta": None, "half_width": None}) == "n/a"
    assert majority([True, True, False]) is True
    assert majority([True, False, None]) is False
    assert majority([None, None]) is None


def test_mlflow_sink_is_optional(runs: Path, monkeypatch):
    from aireview.evals import sinks

    manifest = json.loads((runs / "oracle" / "manifest.json").read_text(encoding="utf-8"))
    scores = json.loads((runs / "oracle" / "scores.json").read_text(encoding="utf-8"))
    metrics = sinks.run_metrics(scores)
    assert metrics["strict.recall"] == 1.0 and "strict.recall.ci_low" in metrics
    assert sinks.run_params(manifest, scores)["config"] == "oracle"
    monkeypatch.setattr(sinks.importlib.util, "find_spec", lambda name: None)
    with pytest.warns(UserWarning, match="mlflow is not installed"):
        assert sinks.log_run(runs / "oracle") is False
