"""Dataset access: case loading, selection, content hash, case.yaml updates and the dev/test split tool."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import random
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from aireview.diffs import IGNORED_DIRS
from aireview.evals.schema import Case, CaseKind
from aireview.settings import repo_root

DATASET_VERSION = "1.0.0"
CASE_FILE = "case.yaml"
MANIFEST_FILE = "manifest.yaml"


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps ISO dates as strings (the schema stores them as str)."""


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


class _Dumper(yaml.SafeDumper):
    """SafeDumper that writes long or multi-line strings as folded blocks, as authors write them."""


def _represent_str(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = ">" if "\n" in value.rstrip("\n") or len(value) > 80 else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _represent_str)


def load_yaml(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=_Loader)


def dump_yaml(data: Any, path: Path) -> None:
    text = yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False, width=100)
    path.write_text(text, encoding="utf-8", newline="\n")


def resolve_root(root: Path | str) -> Path:
    """A relative dataset root is taken from the cwd if it exists there, else from the repo root."""
    root = Path(root)
    if root.is_absolute() or root.exists():
        return root
    return repo_root() / root


def case_dirs(root: Path) -> list[Path]:
    cases = resolve_root(root) / "cases"
    return sorted(p for p in cases.iterdir() if p.is_dir() and (p / CASE_FILE).exists()) if cases.is_dir() else []


def load_case(case_dir: Path) -> Case:
    return Case.model_validate(load_yaml(case_dir / CASE_FILE))


def load_dataset(root: Path = Path("evals/dataset")) -> list[tuple[Case, Path]]:
    """All cases with their directories, sorted by id. Raises ValueError naming the first invalid case."""
    out: list[tuple[Case, Path]] = []
    for case_dir in case_dirs(root):
        try:
            out.append((load_case(case_dir), case_dir))
        except Exception as exc:
            raise ValueError(f"{case_dir.name}: invalid {CASE_FILE}: {exc}") from exc
    return sorted(out, key=lambda item: item[0].id)


def select(
    cases: list[tuple[Case, Path]], split: str | None = None, ids: list[str] | None = None
) -> list[tuple[Case, Path]]:
    """Filter by split ('all' or None = every split) and by explicit ids (unknown ids raise)."""
    out = [item for item in cases if split in (None, "all") or (item[0].split and item[0].split.value == split)]
    if ids:
        known = {case.id for case, _ in cases}
        unknown = sorted(set(ids) - known)
        if unknown:
            raise ValueError(f"unknown case ids: {', '.join(unknown)}")
        out = [item for item in out if item[0].id in ids]
    return out


def dataset_hash(root: Path) -> str:
    """sha256 over the sorted relative paths and bytes of every file under `cases/`."""
    cases = resolve_root(root) / "cases"
    digest = hashlib.sha256()
    files = sorted(
        (p.relative_to(cases).as_posix(), p)
        for p in cases.rglob("*")
        if p.is_file() and not any(part in IGNORED_DIRS for part in p.relative_to(cases).parts) and p.suffix != ".pyc"
    )
    for rel, path in files:
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def dataset_version(root: Path) -> str:
    manifest = resolve_root(root) / MANIFEST_FILE
    data = load_yaml(manifest) if manifest.exists() else None
    return str((data or {}).get("version", DATASET_VERSION))


def read_case_diff(case_dir: Path) -> str:
    return (case_dir / "change.diff").read_text(encoding="utf-8").replace("\r\n", "\n")


def update_case_yaml(case_dir: Path, **fields: Any) -> None:
    """Set top-level keys in case.yaml, keeping existing key order; new keys go to their schema position."""
    data: dict[str, Any] = load_yaml(case_dir / CASE_FILE)
    order = list(Case.model_fields)
    for key, value in fields.items():
        if key in data:
            data[key] = value
            continue
        rank = order.index(key)
        items = list(data.items())
        pos = len(items)
        for idx, (existing, _) in enumerate(items):
            if existing in order and order.index(existing) > rank:
                pos = idx
                break
        items.insert(pos, (key, value))
        data = dict(items)
    dump_yaml(data, case_dir / CASE_FILE)


def stratum(case: Case) -> str:
    """Split stratum: kind x primary (first) bug category; clean cases by kind only."""
    if case.kind == CaseKind.clean or not case.bugs:
        return case.kind.value
    return f"{case.kind.value}:{case.bugs[0].category.value}"


def assign_splits(cases: list[Case], dev_fraction: float, seed: int) -> dict[str, str]:
    """Stratified systematic assignment: order by stratum (shuffled within), take every 1/fraction-th as dev."""
    rng = random.Random(seed)
    offset = rng.random()
    ordered: list[str] = []
    by_stratum: dict[str, list[str]] = {}
    for case in cases:
        by_stratum.setdefault(stratum(case), []).append(case.id)
    for key in sorted(by_stratum):
        ids = sorted(by_stratum[key])
        random.Random(f"{seed}|{key}").shuffle(ids)
        ordered.extend(ids)
    out: dict[str, str] = {}
    for i, case_id in enumerate(ordered):
        is_dev = int((i + 1) * dev_fraction + offset) > int(i * dev_fraction + offset)
        out[case_id] = "dev" if is_dev else "test"
    return out


def write_manifest(root: Path) -> dict[str, Any]:
    """Refresh manifest.yaml from the cases on disk.

    Keeps the original `created` date, and keeps any other top-level key (such as `canary`) with its value
    and position, so hand-written metadata survives a refresh.
    """
    root = resolve_root(root)
    path = root / MANIFEST_FILE
    previous = (load_yaml(path) if path.exists() else None) or {}
    cases = load_dataset(root)
    fresh = {
        "version": str(previous.get("version", DATASET_VERSION)),
        "created": str(previous.get("created", dt.date.today().isoformat())),
        "dataset_hash": dataset_hash(root),
        "counts": {
            "total": len(cases),
            "by_kind": dict(sorted(Counter(c.kind.value for c, _ in cases).items())),
            "by_split": dict(sorted(Counter(c.split.value if c.split else "unassigned" for c, _ in cases).items())),
        },
        "cases": [{"id": c.id, "kind": c.kind.value, "split": c.split.value if c.split else None} for c, _ in cases],
    }
    manifest = {key: fresh.get(key, value) for key, value in previous.items()}
    manifest.update({key: value for key, value in fresh.items() if key not in manifest})
    dump_yaml(manifest, path)
    return manifest


def cli_split(args: argparse.Namespace) -> int:
    root = resolve_root(args.dataset)
    cases = load_dataset(root)
    pool = [case for case, _ in cases if args.force or case.split is None]
    assignment = assign_splits(pool, args.dev_fraction, args.seed)
    dirs = {case.id: case_dir for case, case_dir in cases}
    for case_id, split in sorted(assignment.items()):
        update_case_yaml(dirs[case_id], split=split)
    manifest = write_manifest(root)
    counts = Counter(
        (case.kind.value, assignment.get(case.id, case.split.value if case.split else "-")) for case, _ in cases
    )
    print(f"assigned {len(assignment)} of {len(cases)} cases (seed {args.seed}, dev fraction {args.dev_fraction})")
    for (kind, split), n in sorted(counts.items()):
        print(f"  {kind:<8} {split:<5} {n}")
    print(f"dataset_hash {manifest['dataset_hash']}")
    return 0
