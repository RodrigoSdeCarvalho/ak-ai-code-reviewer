import argparse
from collections import Counter
from pathlib import Path

import pytest
import yaml

from aireview.evals.dataset import (
    assign_splits,
    cli_split,
    dataset_hash,
    dataset_version,
    load_dataset,
    load_yaml,
    read_case_diff,
    select,
    update_case_yaml,
)
from aireview.evals.schema import Case


def _case_yaml(case_id: str, kind: str, category: str | None = None) -> dict:
    data = {
        "id": case_id,
        "kind": kind,
        "title": f"case {case_id}",
        "language": "python",
        "provenance": {"origin": "authored", "source": None, "author": "test", "created": "2026-10-23"},
        "ground_truth": "none" if kind == "clean" else "test-validated",
        "bugs": [],
    }
    if category:
        data["bugs"] = [
            {
                "id": "b1",
                "file": "m.py",
                "line_start": 1,
                "line_end": 1,
                "severity": "high",
                "category": category,
                "description": "wrong",
            }
        ]
    return data


def _make_dataset(root: Path, specs: list[tuple[str, str, str | None]]) -> Path:
    for case_id, kind, category in specs:
        case_dir = root / "cases" / case_id
        case_dir.mkdir(parents=True)
        (case_dir / "case.yaml").write_text(yaml.safe_dump(_case_yaml(case_id, kind, category), sort_keys=False))
        (case_dir / "change.diff").write_text("diff --git a/m.py b/m.py\n", encoding="utf-8")
    return root


def _specs(n_seeded_per_cat: int = 5, n_clean: int = 5) -> list[tuple[str, str, str | None]]:
    specs: list[tuple[str, str, str | None]] = []
    for cat in ("logic", "security", "error_handling"):
        specs += [(f"seeded-{cat}-{i:03d}", "seeded", cat) for i in range(n_seeded_per_cat)]
    specs += [(f"clean-{i:03d}", "clean", None) for i in range(n_clean)]
    return specs


def test_load_dataset_sorted_and_select(tmp_path):
    root = _make_dataset(tmp_path, [("b-case", "clean", None), ("a-case", "seeded", "logic")])
    cases = load_dataset(root)
    assert [c.id for c, _ in cases] == ["a-case", "b-case"]
    assert cases[0][1] == root / "cases" / "a-case"
    assert read_case_diff(cases[0][1]).startswith("diff --git")
    assert select(cases, "all") == cases
    assert select(cases, None, ["b-case"])[0][0].id == "b-case"
    assert select(cases, "dev") == []  # splits unset
    with pytest.raises(ValueError, match="unknown case ids"):
        select(cases, None, ["nope"])


def test_load_dataset_reports_invalid_case(tmp_path):
    root = _make_dataset(tmp_path, [("a", "clean", None)])
    (root / "cases" / "a" / "case.yaml").write_text("id: a\nkind: weird\n")
    with pytest.raises(ValueError, match=r"a: invalid case\.yaml"):
        load_dataset(root)


def test_unquoted_dates_stay_strings(tmp_path):
    root = _make_dataset(tmp_path, [("a", "clean", None)])
    path = root / "cases" / "a" / "case.yaml"
    path.write_text(path.read_text().replace("'2026-10-23'", "2026-10-23"))
    [(case, _)] = load_dataset(root)
    assert case.provenance.created == "2026-10-23"


def test_dataset_hash_tracks_content_and_ignores_pycache(tmp_path):
    root = _make_dataset(tmp_path, [("a", "clean", None)])
    h1 = dataset_hash(root)
    cache = root / "cases" / "a" / "after" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "x.cpython-312.pyc").write_bytes(b"junk")
    assert dataset_hash(root) == h1
    (root / "cases" / "a" / "change.diff").write_text("changed\n")
    assert dataset_hash(root) != h1


def test_dataset_version_defaults_and_reads_manifest(tmp_path):
    assert dataset_version(tmp_path) == "1.0.0"
    (tmp_path / "manifest.yaml").write_text("version: 2.1.0\n")
    assert dataset_version(tmp_path) == "2.1.0"


def test_update_case_yaml_keeps_order_and_inserts_at_schema_position(tmp_path):
    root = _make_dataset(tmp_path, [("a", "seeded", "logic")])
    case_dir = root / "cases" / "a"
    update_case_yaml(case_dir, split="dev", size_bucket="S")
    keys = list(load_yaml(case_dir / "case.yaml"))
    assert keys[:6] == ["id", "kind", "split", "title", "language", "size_bucket"]
    update_case_yaml(case_dir, split="test")
    assert list(load_yaml(case_dir / "case.yaml")) == keys
    assert Case.model_validate(load_yaml(case_dir / "case.yaml")).split == "test"


def test_assign_splits_is_deterministic_and_stratified():
    cases = [Case.model_validate(_case_yaml(i, k, c)) for i, k, c in _specs()]
    first = assign_splits(cases, 0.4, seed=1)
    assert first == assign_splits(list(reversed(cases)), 0.4, seed=1)
    assert Counter(first.values())["dev"] == 8  # 20 cases x 0.4
    for prefix in ("seeded-logic", "seeded-security", "seeded-error_handling", "clean"):
        devs = sum(1 for cid, s in first.items() if cid.startswith(prefix) and s == "dev")
        assert devs == 2  # 5 per stratum x 0.4
    assert assign_splits(cases, 0.4, seed=2) != first


def test_cli_split_only_assigns_unset_unless_forced(tmp_path):
    root = _make_dataset(tmp_path, _specs(n_seeded_per_cat=3, n_clean=3))
    update_case_yaml(root / "cases" / "clean-000", split="dev")
    args = argparse.Namespace(dataset=str(root), dev_fraction=0.4, seed=7, force=False)
    assert cli_split(args) == 0
    cases = {c.id: c for c, _ in load_dataset(root)}
    assert cases["clean-000"].split == "dev"
    assert all(c.split is not None for c in cases.values())

    manifest = load_yaml(root / "manifest.yaml")
    assert manifest["version"] == "1.0.0"
    assert manifest["dataset_hash"] == dataset_hash(root)
    assert [row["id"] for row in manifest["cases"]] == sorted(cases)
    assert manifest["counts"]["total"] == 12

    snapshot = {cid: c.split for cid, c in cases.items()}
    assert cli_split(args) == 0
    assert {c.id: c.split for c, _ in load_dataset(root)} == snapshot

    assert cli_split(argparse.Namespace(dataset=str(root), dev_fraction=0.4, seed=7, force=True)) == 0
    assert sum(1 for c, _ in load_dataset(root) if c.split == "dev") in (4, 5)  # 12 x 0.4


def test_manifest_refresh_keeps_unknown_top_level_keys(tmp_path):
    root = _make_dataset(tmp_path, _specs(n_seeded_per_cat=1, n_clean=1))
    canary = "Evaluation data; do not train on it. canary GUID 00000000-0000-4000-8000-000000000000"
    (root / "manifest.yaml").write_text(
        f"version: 1.2.0\ncreated: '2026-01-02'\ncanary: {canary}\ndataset_hash: stale\ncases: []\n",
        encoding="utf-8",
    )
    assert cli_split(argparse.Namespace(dataset=str(root), dev_fraction=0.4, seed=7, force=False)) == 0
    manifest = load_yaml(root / "manifest.yaml")
    assert manifest["canary"] == canary
    assert list(manifest)[:4] == ["version", "created", "canary", "dataset_hash"]
    assert manifest["version"] == "1.2.0" and manifest["created"] == "2026-01-02"
    assert manifest["dataset_hash"] == dataset_hash(root)
    assert len(manifest["cases"]) == 4
