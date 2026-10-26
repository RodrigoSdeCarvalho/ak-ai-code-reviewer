"""End-to-end eval runs on a tiny dataset written by the test: synthetic backends, replay, budget stop, CLI."""

import argparse
import json
from pathlib import Path

import pytest
import yaml

from aireview.cli import _build_parser
from aireview.diffs import diff_dirs
from aireview.evals import runner
from aireview.evals.baselines import ExactMatchJudge, null_review, oracle_review, spam_review
from aireview.evals.dataset import load_dataset
from aireview.evals.judge import JUDGE_PROMPT_VERSION, TRIAGE_PROMPT_VERSION, Judge, candidate_items
from aireview.evals.report import load_reviews, read_jsonl
from aireview.evals.schema import ReviewerConfig
from aireview.llm.base import LLMResponse
from aireview.llm.cassette import BudgetExceeded, CassetteStore, ReplayClient
from aireview.models import Usage

CALC_BEFORE = "def total(items):\n    return sum(items)\n"
CALC_AFTER = (
    "def total(items):\n"
    "    return sum(items)\n"
    "\n"
    "\n"
    "def average(items):\n"
    "    if not items:\n"
    "        return 0.0\n"
    "    return sum(items) / (len(items) + 1)\n"
)
AUTH_BEFORE = "TOKENS = {}\n\n\ndef login(user):\n    return TOKENS.get(user)\n"
AUTH_AFTER = (
    "import subprocess\n"
    "\n"
    "TOKENS = {}\n"
    "\n"
    "\n"
    "def login(user):\n"
    "    return TOKENS.get(user)\n"
    "\n"
    "\n"
    "def ping(host):\n"
    '    return subprocess.run(f"ping -c 1 {host}", shell=True, check=False).returncode\n'
    "\n"
    "\n"
    "def read_config(path):\n"
    "    try:\n"
    "        with open(path) as fh:\n"
    "            return fh.read()\n"
    "    except Exception:\n"
    "        return None\n"
)
CLEAN_BEFORE = "def greet(name):\n    return 'hi ' + name\n"
CLEAN_AFTER = 'def greet(name: str) -> str:\n    """Greeting for `name`."""\n    return f"hi {name}"\n'

CASES = {
    "seeded-calc": (
        "app/calc.py",
        CALC_BEFORE,
        CALC_AFTER,
        [
            {
                "id": "b1",
                "file": "app/calc.py",
                "line_start": 8,
                "line_end": 8,
                "severity": "high",
                "category": "logic",
                "description": "average divides by len(items) + 1, so every mean is too small.",
            }
        ],
    ),
    "seeded-auth": (
        "app/auth.py",
        AUTH_BEFORE,
        AUTH_AFTER,
        [
            {
                "id": "b1",
                "file": "app/auth.py",
                "line_start": 11,
                "line_end": 11,
                "severity": "critical",
                "category": "security",
                "description": "ping interpolates host into a shell command: command injection.",
            },
            {
                "id": "b2",
                "file": "app/auth.py",
                "line_start": 18,
                "line_end": 19,
                "severity": "medium",
                "category": "error_handling",
                "description": "read_config swallows every exception and returns None, hiding a missing file.",
            },
        ],
    ),
    "clean-greet": ("app/greet.py", CLEAN_BEFORE, CLEAN_AFTER, []),
}


def make_dataset(root: Path) -> Path:
    """2 seeded + 1 clean case under `root` (case.yaml, before/, after/, change.diff, manifest.yaml)."""
    for case_id, (rel, before, after, bugs) in CASES.items():
        case_dir = root / "cases" / case_id
        for side, text in (("before", before), ("after", after)):
            path = case_dir / side / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        (case_dir / "change.diff").write_text(
            diff_dirs(case_dir / "before", case_dir / "after"), encoding="utf-8", newline="\n"
        )
        case = {
            "id": case_id,
            "kind": "clean" if not bugs else "seeded",
            "split": "test",
            "title": case_id,
            "size_bucket": "S",
            "provenance": {"origin": "authored", "author": "test", "created": "2026-10-23"},
            "ground_truth": "none" if not bugs else "test-validated",
            "bugs": bugs,
        }
        (case_dir / "case.yaml").write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    (root / "manifest.yaml").write_text("version: 0.0.1\n", encoding="utf-8")
    return root


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    return make_dataset(tmp_path / "dataset")


def make_plan(dataset: Path, run_dir: Path, backend: str, samples: int = 2, **config) -> runner.RunPlan:
    return runner.RunPlan(
        run_id=run_dir.name,
        run_dir=run_dir,
        config=ReviewerConfig(name=backend, backend=backend, **config),
        cases=load_dataset(dataset),
        dataset_root=dataset,
        split="test",
        samples=samples,
        mode="replay",
        n_boot=200,
    )


def run_synthetic(dataset: Path, tmp_path: Path, backend: str) -> runner.RunResult:
    return runner.execute(make_plan(dataset, tmp_path / "runs" / backend, backend), None, ExactMatchJudge())


class FakeJudgeClient:
    """Answers every judge request with a fixed verdict."""

    def __init__(self, verdict: str = "same"):
        self.verdict = verdict
        self.calls = 0

    def complete(self, request):
        self.calls += 1
        return LLMResponse(
            parsed={"reason": "r", "verdict": self.verdict}, usage=Usage(cost_usd=0.001), served_model=request.model
        )

    def complete_many(self, requests):
        return [self.complete(r) for r in requests]


# ---------------------------------------------------------------- baselines


def test_baseline_reviewers(dataset: Path):
    cases = dict((c.id, (c, d)) for c, d in load_dataset(dataset))
    auth, auth_dir = cases["seeded-auth"]
    oracle = oracle_review(auth)
    assert [(f.file, f.line, f.severity.value) for f in oracle.findings] == [
        ("app/auth.py", 11, "critical"),
        ("app/auth.py", 18, "medium"),
    ]
    assert oracle.findings[0].description == auth.bugs[0].description
    assert null_review().findings == []
    spam = spam_review((auth_dir / "change.diff").read_text(encoding="utf-8"))
    assert len(spam.findings) >= 10
    assert {f.severity.value for f in spam.findings} == {"low"}


# ---------------------------------------------------------------- end-to-end synthetic runs


def test_oracle_scores_perfectly(dataset: Path, tmp_path: Path):
    result = run_synthetic(dataset, tmp_path, "oracle")
    for mode in ("strict", "location"):
        m = result.scores["metrics"][mode]
        assert m["recall"]["value"] == 1.0
        assert m["precision"]["value"] == 1.0
        assert m["clean_false_alarm_rate"]["value"] == 0.0
        assert m["pass_all_k"]["value"] == 1.0
    run_dir = tmp_path / "runs" / "oracle"
    for name in ("manifest.json", "reviews.jsonl", "errors.jsonl", "judgments.jsonl", "scores.json", "report.md"):
        assert (run_dir / name).is_file(), name
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["judge_model"] == "exact-match"
    assert manifest["case_ids"] == ["clean-greet", "seeded-auth", "seeded-calc"]
    assert manifest["extra"]["incomplete"] is False
    assert len(manifest["config_hash"]) == 64
    assert "# Eval run `oracle`" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_null_finds_nothing(dataset: Path, tmp_path: Path):
    m = run_synthetic(dataset, tmp_path, "null").scores["metrics"]["strict"]
    assert m["recall"]["value"] == 0.0
    assert m["precision"]["value"] is None
    assert m["clean_false_alarm_rate"]["value"] == 0.0


def test_spam_hits_locations_but_not_the_judge(dataset: Path, tmp_path: Path):
    result = run_synthetic(dataset, tmp_path, "spam")
    assert result.scores["metrics"]["location"]["recall"]["value"] == 1.0
    assert result.scores["metrics"]["location"]["precision"]["value"] <= 0.3
    assert result.scores["metrics"]["strict"]["recall"]["value"] == 0.0


# ---------------------------------------------------------------- the model path, offline


def _oracle_parsed(case):
    return {"findings": [f.model_dump(mode="json") for f in oracle_review(case).findings]}


def test_anthropic_backend_replays_cassettes(dataset: Path, tmp_path: Path):
    plan = make_plan(dataset, tmp_path / "runs" / "replay", "anthropic", model="claude-sonnet-5-5", prompt_version="v1")
    store = CassetteStore(tmp_path / "cassettes")
    jobs = runner.reviewer_requests(plan)
    for case, _, sample, _, request in jobs:
        if case.id == "seeded-calc" and sample == 1:
            continue  # left unrecorded: must surface as an error row, never as "no findings"
        store.put(
            request,
            LLMResponse(
                parsed=_oracle_parsed(case),
                usage=Usage(input_tokens=100, output_tokens=50, cost_usd=0.01, latency_ms=1000),
                served_model="claude-sonnet-5-5",
            ),
        )
    judge_client = FakeJudgeClient("same")
    result = runner.execute(plan, ReplayClient(store), Judge(judge_client))

    assert result.scores["status_counts"]["api_error"] == 1
    assert result.scores["metrics"]["strict"]["recall"]["value"] == 1.0
    errors = read_jsonl(plan.run_dir / "errors.jsonl")
    assert errors == [
        {
            "case_id": "seeded-calc",
            "sample": 1,
            "status": "api_error",
            "failure_class": "cassette_missing",
            "attempts": 0,
            "error": errors[0]["error"],
        }
    ]
    rows = load_reviews(plan.run_dir)
    assert all(r.cassette_key for r in rows)
    assert {r.attempts for r in rows if r.status.value == "ok"} == {1}  # per-row API attempts are recorded
    assert (
        result.manifest.prompt_hash and result.manifest.judge_prompt_version == JUDGE_PROMPT_VERSION == "same-defect-v2"
    )
    assert 0 < judge_client.calls <= result.scores["ops"]["judge_calls"]  # identical pairs are sent once


class BudgetStopClient:
    """Answers the first `ok_calls` complete_many calls, then raises BudgetExceeded."""

    def __init__(self, ok_calls: int):
        self.ok_calls = ok_calls

    def complete_many(self, requests):
        if self.ok_calls == 0:
            raise BudgetExceeded("spent")
        self.ok_calls -= 1
        return [LLMResponse(parsed={"findings": []}, usage=Usage(cost_usd=0.01)) for _ in requests]


def test_budget_stop_writes_partial_incomplete_run(dataset: Path, tmp_path: Path):
    plan = make_plan(dataset, tmp_path / "runs" / "partial", "anthropic", samples=1)
    result = runner.execute(plan, BudgetStopClient(1), Judge(FakeJudgeClient()), chunk_size=2)
    assert result.incomplete
    assert len(result.rows) == 2
    assert result.scores["status_counts"]["missing"] == 1
    assert result.manifest.extra["incomplete"] is True
    errors = read_jsonl(plan.run_dir / "errors.jsonl")
    assert [(e["case_id"], e["status"], e["failure_class"]) for e in errors] == [("seeded-calc", "missing", "missing")]


def test_estimate_cost_scales_with_requests(dataset: Path, tmp_path: Path):
    plan = make_plan(dataset, tmp_path / "x", "anthropic", samples=3, model="claude-sonnet-5-5", prompt_version="v1")
    requests = [job[4] for job in runner.reviewer_requests(plan)]
    est = runner.estimate_cost(requests, "claude-haiku-5-5")
    assert est["reviews"] == 9
    assert est["judge_pairs"] == 27
    assert est["total_usd"] == pytest.approx(est["reviewer_usd"] + est["judge_usd"])
    assert runner.estimate_cost(requests, "claude-haiku-5-5", batch=True)["total_usd"] == pytest.approx(
        est["total_usd"] / 2
    )


def test_default_run_id_format():
    from datetime import UTC, datetime

    config = ReviewerConfig(name="v1-sonnet", backend="anthropic")
    when = datetime(2026, 10, 23, 9, 5, 7, tzinfo=UTC)
    assert runner.default_run_id(config, "test", 3, "replay", when) == "v1-sonnet-test-k3-replay-20261023T090507"


# ---------------------------------------------------------------- CLI


def _args(*argv: str) -> argparse.Namespace:
    return _build_parser().parse_args(["eval", *argv])


def test_cli_run_and_rescore(dataset: Path, tmp_path: Path):
    runs = tmp_path / "runs"
    config = Path(__file__).resolve().parents[1] / "evals" / "configs" / "oracle.yaml"
    args = _args("run", "--config", str(config), "--dataset", str(dataset), "--split", "test", "--samples", "2")
    args.runs_dir, args.run_id = str(runs), "cli-oracle"
    assert runner.cli_run(args) == 0
    scores = json.loads((runs / "cli-oracle" / "scores.json").read_text(encoding="utf-8"))
    assert scores["metrics"]["strict"]["recall"]["value"] == 1.0

    assert runner.cli_score(_args("score", str(runs / "cli-oracle"), "--tolerance", "0")) == 0
    rescored = json.loads((runs / "cli-oracle" / "scores.json").read_text(encoding="utf-8"))
    assert rescored["tolerance"] == 0
    manifest = json.loads((runs / "cli-oracle" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tolerance"] == 0 and "rescored_at" in manifest["extra"]


def test_cli_run_refuses_over_budget_before_any_call(dataset: Path, tmp_path: Path, capsys):
    config = Path(__file__).resolve().parents[1] / "evals" / "configs" / "v1-sonnet.yaml"
    args = _args(
        "run", "--config", str(config), "--dataset", str(dataset), "--mode", "record", "--budget-usd", "0.0001"
    )
    args.runs_dir = str(tmp_path / "runs")
    assert runner.cli_run(args) == 1
    assert "refusing to start" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists()


def test_cli_run_usage_errors(dataset: Path, tmp_path: Path):
    config = Path(__file__).resolve().parents[1] / "evals" / "configs" / "oracle.yaml"
    bad_case = _args("run", "--config", str(config), "--dataset", str(dataset), "--case", "nope")
    assert runner.cli_run(bad_case) == 3
    bad_tol = _args("run", "--config", str(config), "--dataset", str(dataset), "--tolerance", "11")
    assert runner.cli_run(bad_tol) == 3
    assert runner.cli_run(_args("run", "--config", str(tmp_path / "missing.yaml"))) == 3


# ---------------------------------------------------------------- regressions


def _replayed_run(dataset: Path, tmp_path: Path) -> runner.RunPlan:
    """An anthropic-backend run whose reviews are the oracle findings, judged `same`, written to disk."""
    plan = make_plan(
        dataset, tmp_path / "runs" / "rescore", "anthropic", model="claude-sonnet-5-5", prompt_version="v1"
    )
    store = CassetteStore(tmp_path / "cassettes")
    for case, _, _, _, request in runner.reviewer_requests(plan):
        store.put(request, LLMResponse(parsed=_oracle_parsed(case), served_model="claude-sonnet-5-5"))
    runner.execute(plan, ReplayClient(store), Judge(FakeJudgeClient("same")))
    return plan


def test_rescore_rejudges_pairs_whose_label_changed(dataset: Path, tmp_path: Path, monkeypatch):
    plan = _replayed_run(dataset, tmp_path)
    rejudge = FakeJudgeClient("different")
    monkeypatch.setattr(runner, "make_judge", lambda *a, **kw: Judge(rejudge))

    assert runner.cli_score(_args("score", str(plan.run_dir))) == 0
    assert rejudge.calls == 0  # labels unchanged: every stored verdict is still valid

    case_yaml = dataset / "cases" / "seeded-calc" / "case.yaml"
    case = yaml.safe_load(case_yaml.read_text(encoding="utf-8"))
    case["bugs"][0]["description"] = "EDITED: average divides by the wrong count."
    case_yaml.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    assert runner.cli_score(_args("score", str(plan.run_dir))) == 0
    assert rejudge.calls == 1  # only the edited bug's pair (identical pairs across samples are sent once)
    scores = json.loads((plan.run_dir / "scores.json").read_text(encoding="utf-8"))
    per_bug = {(b["case_id"], b["bug_id"]): b for b in scores["per_bug"]}
    assert per_bug[("seeded-calc", "b1")]["strict"]["detect_rate"] == 0.0
    assert per_bug[("seeded-auth", "b1")]["strict"]["detect_rate"] == 1.0
    manifest = json.loads((plan.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extra"]["original_dataset_hash"] != manifest["dataset_hash"]


def test_stored_verdicts_are_reused_only_for_an_identical_request(dataset: Path):
    cases = load_dataset(dataset)
    case, case_dir = next((c, d) for c, d in cases if c.id == "seeded-calc")
    items = candidate_items(case, case_dir, 0, oracle_review(case).findings)
    judge = Judge(FakeJudgeClient())
    stored = judge.judge_many(items)
    assert runner.reusable_judgments(judge, items, stored) == (stored, [])
    stale = [j.model_copy(update={"cassette_key": "old"}) for j in stored]
    assert runner.reusable_judgments(judge, items, stale) == ([], items)
    # The exact-match judge is free and keyless: always judged again.
    assert runner.reusable_judgments(ExactMatchJudge(), items, stored) == ([], items)


def test_sample_offset_gives_new_request_keys_and_is_recorded(dataset: Path, tmp_path: Path):
    base = make_plan(dataset, tmp_path / "a", "anthropic", model="claude-sonnet-5-5", prompt_version="v1")
    shifted = make_plan(dataset, tmp_path / "b", "anthropic", model="claude-sonnet-5-5", prompt_version="v1")
    shifted.sample_offset = 2
    a, b = runner.reviewer_requests(base), runner.reviewer_requests(shifted)
    assert [job[2] for job in a] == [job[2] for job in b]  # row sample indices stay 0..k-1
    assert [job[4].sample for job in b] == [s + 2 for s in (job[2] for job in b)]
    assert not {job[4].key() for job in a} & {job[4].key() for job in b}
    store = CassetteStore(tmp_path / "cassettes")
    result = runner.execute(shifted, ReplayClient(store), Judge(FakeJudgeClient()))
    assert result.manifest.sample_offset == 2


def _record_args(dataset: Path, tmp_path: Path, *extra: str) -> argparse.Namespace:
    config = Path(__file__).resolve().parents[1] / "evals" / "configs" / "v1-sonnet.yaml"
    args = _args("run", "--config", str(config), "--dataset", str(dataset), "--mode", "record", *extra)
    args.runs_dir = str(tmp_path / "runs")
    return args


def test_cli_run_prints_estimate_with_judge_and_batch_before_recording(
    dataset: Path, tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setattr(runner, "confirm", lambda question: False)
    assert runner.cli_run(_record_args(dataset, tmp_path, "--batch", "--budget-usd", "50")) == 1
    out = capsys.readouterr().out
    line = next(x for x in out.splitlines() if x.startswith("estimate:"))
    assert "judge ~" in line and line.count("(batch -50%)") == 2
    assert out.index("estimate:") < out.index("aborted")
    assert not (tmp_path / "runs").exists()


def test_cli_run_refuses_an_unpriced_judge_before_any_spend(dataset: Path, tmp_path: Path, capsys):
    args = _record_args(dataset, tmp_path, "--judge-model", "claude-sonnet-9", "--yes")
    assert runner.cli_run(args) == 3
    assert "no price for model 'claude-sonnet-9'" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


def test_cli_run_record_refuses_to_overwrite_cassettes(dataset: Path, tmp_path: Path, monkeypatch, capsys):
    class Recorded(CassetteStore):
        def exists(self, request):
            return True

    monkeypatch.setattr(runner, "CassetteStore", lambda: Recorded(tmp_path / "cassettes"))
    assert runner.cli_run(_record_args(dataset, tmp_path, "--yes", "--budget-usd", "50")) == 3
    assert "write-once" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists()


# ---------------------------------------------------------------- eval score: re-judge + FP triage


class JudgeAndTriageClient:
    """Fake judge client: a fixed verdict for same-defect requests, a fixed label for triage requests."""

    def __init__(self, verdict: str = "different", label: str = "nit"):
        self.verdict, self.label = verdict, label
        self.judge_calls = self.triage_calls = 0

    def complete(self, request):
        if request.prompt_version == TRIAGE_PROMPT_VERSION:
            self.triage_calls += 1
            parsed = {"reason": "r", "label": self.label}
        else:
            self.judge_calls += 1
            parsed = {"reason": "r", "verdict": self.verdict}
        return LLMResponse(parsed=parsed, usage=Usage(cost_usd=0.001), served_model=request.model)

    def complete_many(self, requests):
        return [self.complete(r) for r in requests]


def _age_to_v1(run_dir: Path) -> None:
    """Make a run look judged by the previous prompt: old judgment keys and judge_prompt_version."""
    path = run_dir / "judgments.jsonl"
    rows = [
        json.loads(x) | {"cassette_key": "v1-" + json.loads(x)["cassette_key"]} for x in path.read_text().splitlines()
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["judge_prompt_version"] = "same-defect-v1"
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_score_rejudges_with_the_current_prompt_and_triages_fps(dataset: Path, tmp_path: Path, monkeypatch, capsys):
    plan = _replayed_run(dataset, tmp_path)
    _age_to_v1(plan.run_dir)
    client = JudgeAndTriageClient(verdict="different", label="nit")
    calls = []

    def fake_make_judge(backend, mode, judge_model, store, **kw):
        calls.append((mode, kw))
        return Judge(client, model=judge_model)

    monkeypatch.setattr(runner, "make_judge", fake_make_judge)
    assert runner.cli_score(_args("score", str(plan.run_dir), "--triage-fp")) == 0
    assert calls[0][0] == "replay"
    assert client.judge_calls == 5  # every stale v1 pair is judged again (identical pairs across samples once)
    for name in ("judgments.jsonl", "triage.jsonl", "scores.json", "report.md", "manifest.json"):
        assert (plan.run_dir / name).is_file(), name
    manifest = json.loads((plan.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["judge_prompt_version"] == JUDGE_PROMPT_VERSION == "same-defect-v2"
    assert manifest["extra"]["triage_prompt_version"] == TRIAGE_PROMPT_VERSION
    judgments = read_jsonl(plan.run_dir / "judgments.jsonl")
    assert judgments and not any(j["cassette_key"].startswith("v1-") for j in judgments)
    assert {j["verdict"] for j in judgments} == {"different"}
    triage = read_jsonl(plan.run_dir / "triage.jsonl")
    scores = json.loads((plan.run_dir / "scores.json").read_text(encoding="utf-8"))
    n_fp = sum(
        o == "fp"
        for c in scores["per_case"]
        for s in c["samples"]
        for o in (s.get("strict") or {}).get("finding_outcomes", [])
    )
    assert n_fp > 0 and len(triage) == n_fp and {t["label"] for t in triage} == {"nit"}
    assert "FP triage (advisory" in (plan.run_dir / "report.md").read_text(encoding="utf-8")

    # A second re-score reuses every judgment and triage row: no calls at all.
    client.judge_calls = client.triage_calls = 0
    assert runner.cli_score(_args("score", str(plan.run_dir), "--triage-fp")) == 0
    assert (client.judge_calls, client.triage_calls) == (0, 0)
    assert len(read_jsonl(plan.run_dir / "triage.jsonl")) == n_fp


def test_score_without_triage_drops_rows_of_findings_that_are_no_longer_fps(dataset: Path, tmp_path: Path, monkeypatch):
    plan = _replayed_run(dataset, tmp_path)
    client = JudgeAndTriageClient(verdict="different")
    monkeypatch.setattr(runner, "make_judge", lambda *a, **kw: Judge(client))
    _age_to_v1(plan.run_dir)
    assert runner.cli_score(_args("score", str(plan.run_dir), "--triage-fp")) == 0
    assert read_jsonl(plan.run_dir / "triage.jsonl")
    client.verdict = "same"
    _age_to_v1(plan.run_dir)
    assert runner.cli_score(_args("score", str(plan.run_dir))) == 0  # every finding now matches: no FP left
    assert not (plan.run_dir / "triage.jsonl").exists()


def test_score_replay_with_missing_cassettes_records_errors_not_labels(dataset: Path, tmp_path: Path, monkeypatch):
    plan = _replayed_run(dataset, tmp_path)
    _age_to_v1(plan.run_dir)
    monkeypatch.setattr(runner, "CassetteStore", lambda: CassetteStore(tmp_path / "empty-cassettes"))
    assert runner.cli_score(_args("score", str(plan.run_dir), "--triage-fp")) == 0
    judgments = read_jsonl(plan.run_dir / "judgments.jsonl")
    assert judgments and all(j["verdict"] is None and "cassette_missing" in j["error"] for j in judgments)
    triage = read_jsonl(plan.run_dir / "triage.jsonl")
    assert triage and all(t["label"] is None and "cassette_missing" in t["error"] for t in triage)


def test_score_record_refuses_without_a_key(dataset: Path, tmp_path: Path, monkeypatch, capsys):
    plan = _replayed_run(dataset, tmp_path)
    before = (plan.run_dir / "scores.json").read_bytes()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert runner.cli_score(_args("score", str(plan.run_dir), "--mode", "record", "--triage-fp", "--yes")) == 3
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
    assert (plan.run_dir / "scores.json").read_bytes() == before


def test_score_record_resumes_judge_cassettes_and_states_the_estimate(
    dataset: Path, tmp_path: Path, monkeypatch, capsys
):
    plan = _replayed_run(dataset, tmp_path)
    _age_to_v1(plan.run_dir)
    client = JudgeAndTriageClient()
    seen = {}

    def fake_make_client(mode, **kw):
        seen.update(kw, mode=mode)
        return client

    monkeypatch.setattr(runner, "make_client", fake_make_client)
    assert runner.cli_score(_args("score", str(plan.run_dir), "--mode", "record", "--triage-fp", "--yes")) == 0
    assert seen["mode"] == "record" and seen["resume"] is True  # judge cassettes are reused, never overwritten
    assert seen["budget"] is not None
    out = capsys.readouterr().out
    assert out.index("estimate: judge 10 pairs + triage <=") < out.index("re-judged 10 pairs")
    manifest = json.loads((plan.run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["extra"]["score_estimate"]["judge_pairs"] == 10 and "score_spent_usd" in manifest["extra"]


def test_score_record_refuses_over_budget_before_any_call(dataset: Path, tmp_path: Path, monkeypatch, capsys):
    plan = _replayed_run(dataset, tmp_path)
    _age_to_v1(plan.run_dir)
    client = JudgeAndTriageClient()
    monkeypatch.setattr(runner, "make_client", lambda mode, **kw: client)
    args = _args("score", str(plan.run_dir), "--mode", "record", "--triage-fp", "--yes", "--budget-usd", "0.00001")
    assert runner.cli_score(args) == 1
    assert "refusing to start" in capsys.readouterr().out
    assert client.judge_calls == client.triage_calls == 0
