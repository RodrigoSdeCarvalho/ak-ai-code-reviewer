"""Judge calibration: kappa and agreement on hand-computed examples, stratified sampling, blind labelling."""

import argparse
import json
from pathlib import Path

import pytest

from aireview.evals.calibration import (
    agreement,
    allocate,
    calibrate,
    cli_calibrate,
    cohen_kappa,
    cross_judge_verdicts,
    label_pairs,
    render_pair,
    run_pairs,
    sample_pairs,
)
from aireview.evals.judge import Judge
from test_runner import FakeJudgeClient, make_dataset, run_synthetic


def test_cohen_kappa_hand_computed():
    # 10 items: (s,s) x4, (s,d) x2, (d,s) x1, (d,d) x3.
    # observed = 7/10; expected = (6*5 + 4*5) / 100 = 0.5; kappa = (0.7 - 0.5) / 0.5 = 0.4
    a = ["s"] * 6 + ["d"] * 4
    b = ["s"] * 4 + ["d"] * 2 + ["s"] + ["d"] * 3
    assert cohen_kappa(a, b) == pytest.approx(0.4)
    assert cohen_kappa(a, a) == pytest.approx(1.0)
    assert cohen_kappa(["s", "s"], ["s", "s"]) is None  # chance agreement 1: undefined
    assert cohen_kappa([], []) is None


def test_agreement_error_direction():
    pairs = (
        [("same", "same")] * 4
        + [("same", "different")] * 2
        + [("different", "same")]
        + [("different", "different")] * 3
    )
    result = agreement([*pairs, ("unsure", "same")])
    assert result["n"] == 11
    assert result["tpr"] == pytest.approx(4 / 6)
    assert result["tnr"] == pytest.approx(3 / 4)
    assert result["lenient_errors"] == 1  # judge same, human different
    assert result["harsh_errors"] == 2
    assert result["confusion"]["unsure"]["same"] == 1
    assert agreement(pairs)["kappa_binary"] == pytest.approx(0.4)


def test_allocate_quotas():
    assert allocate(10, {"same": 10, "different": 10, "unsure": 10}) == {"same": 4, "different": 4, "unsure": 2}
    assert allocate(10, {"same": 10, "different": 1, "unsure": 0}) == {"same": 9, "different": 1, "unsure": 0}
    assert sum(allocate(50, {"same": 3, "different": 4, "unsure": 5}).values()) == 12


@pytest.fixture(scope="module")
def spam_run(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("calib")
    run_synthetic(make_dataset(root / "dataset"), root, "spam")
    return root / "runs" / "spam"


def test_sample_pairs_stratifies_and_excludes(spam_run: Path):
    pairs = run_pairs(spam_run)
    assert pairs and all(p.verdict == "different" for p in pairs)
    chosen = sample_pairs(pairs, 5, seed=1)
    assert len(chosen) == 5
    assert len({p.pair_id for p in chosen}) == 5
    assert {p.distance for p in chosen} & {0} and max(p.distance for p in chosen) > 0  # spread over distances
    again = sample_pairs(pairs, 5, seed=1, exclude={p.pair_id for p in chosen})
    assert not {p.pair_id for p in again} & {p.pair_id for p in chosen}


def test_label_pairs_is_blind_and_appends(spam_run: Path, tmp_path: Path):
    pairs = sample_pairs(run_pairs(spam_run), 3, seed=2)
    shown: list[str] = []
    answers = iter(["x", "s", "d", "q"])
    labels = tmp_path / "labels.jsonl"
    n = label_pairs(pairs, "rodrigo", labels, read=lambda _: next(answers), write=shown.append)
    assert n == 2
    rows = [json.loads(line) for line in labels.read_text(encoding="utf-8").splitlines()]
    assert [r["label"] for r in rows] == ["same", "different"]
    assert set(rows[0]) >= {
        "pair_id",
        "run_id",
        "case_id",
        "sample",
        "finding_index",
        "bug_id",
        "label",
        "rater",
        "labelled_at",
    }
    assert "LABELLED DEFECT" in render_pair(pairs[0])
    assert shown and all("different" not in text and "verdict" not in text.lower() for text in shown)


def test_calibrate_end_to_end_with_cross_judge(spam_run: Path, tmp_path: Path):
    pairs = sample_pairs(run_pairs(spam_run), 4, seed=3)
    labels_path = tmp_path / "labels.jsonl"
    answers = iter(["d", "d", "d", "s"])
    label_pairs(pairs, "rodrigo", labels_path, read=lambda _: next(answers), write=lambda _: None)
    labels = [json.loads(line) for line in labels_path.read_text(encoding="utf-8").splitlines()]

    cross = cross_judge_verdicts(labels, Judge(FakeJudgeClient("same"), model="claude-opus-5-5"))
    result = calibrate(labels, cross)
    primary = result["primary"]
    assert primary["n"] == 4
    assert primary["raw_agreement"] == pytest.approx(0.75)  # judge said different everywhere
    assert primary["harsh_errors"] == 1 and primary["lenient_errors"] == 0
    assert primary["tnr"] == 1.0 and primary["tpr"] == 0.0
    assert result["cross_judge"]["vs_human"]["lenient_errors"] == 3
    assert result["cross_judge"]["n"] == 4

    out = tmp_path / "calibration.json"
    ns = argparse.Namespace(labels=str(labels_path), cross_judge=None, mode="replay", out=str(out))
    assert cli_calibrate(ns) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["n_joined"] == 4
