"""Data contract of the eval: dataset cases, run rows, judgments, outcomes and configs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aireview.models import Category, Finding, ReviewStatus, Severity, Usage

# ---------------------------------------------------------------- dataset


class CaseKind(StrEnum):
    seeded = "seeded"  # bug introduced into fresh code, validated by a failing test
    clean = "clean"  # correct change, no labelled defect
    real = "real"  # reverted fix from a public repository


class Split(StrEnum):
    dev = "dev"
    test = "test"


class BugTag(StrEnum):
    """Why a label may be out of a reviewer's reach; reported as its own bug slice (`slices.tag`)."""

    unshown_context = "unshown_context"  # the defect depends on code the review prompt does not show
    library_knowledge = "library_knowledge"  # judging it needs knowledge of a third-party library's internals


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str  # authored | reverted-fix
    source: str | None = None  # real: repo URL + fix commit sha + commit date
    author: str
    created: str  # ISO date


class Bug(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    file: str
    line_start: int = Field(ge=1)  # post-change (after/) line numbers
    line_end: int = Field(ge=1)
    severity: Severity
    category: Category
    description: str
    must_find: bool = True
    tags: list[BugTag] = Field(default_factory=list)


class Case(BaseModel):
    """`case.yaml`. Paths inside a case are relative to the case directory."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kind: CaseKind
    split: Split | None = None  # assigned by the split tool
    title: str
    language: str = "python"
    size_bucket: str | None = None  # S | M | L, computed by the validator
    provenance: Provenance
    ground_truth: str  # test-validated | fix-derived | none
    bugs: list[Bug] = Field(default_factory=list)
    notes: str | None = None


# ---------------------------------------------------------------- configs


class ReviewerConfig(BaseModel):
    """`evals/configs/<name>.yaml`."""

    model_config = ConfigDict(extra="forbid")

    name: str
    backend: str  # anthropic | claude-cli | static | oracle | null | spam
    model: str | None = None
    prompt_version: str | None = None
    effort: str | None = None
    max_tokens: int = 16000


# ---------------------------------------------------------------- run rows


class ReviewRow(BaseModel):
    """One (case, sample) review in `reviews.jsonl`."""

    case_id: str
    sample: int
    status: ReviewStatus
    findings: list[Finding] = Field(default_factory=list)
    out_of_scope_findings: list[Finding] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    served_model: str | None = None
    cassette_key: str | None = None
    attempts: int | None = None  # API attempts of the call (None: no model call, e.g. synthetic backends)
    error: str | None = None


class Verdict(StrEnum):
    same = "same"
    different = "different"
    unsure = "unsure"


class Judgment(BaseModel):
    """One judged (finding, bug) candidate pair in `judgments.jsonl`."""

    case_id: str
    sample: int
    finding_index: int
    bug_id: str
    verdict: Verdict | None = None  # None = judge error (see error)
    reason: str | None = None
    swapped: bool = False  # position-bias control: True if the finding was shown as "A"
    usage: Usage = Field(default_factory=Usage)
    cassette_key: str | None = None
    attempts: int | None = None
    error: str | None = None


class FindingOutcome(StrEnum):
    tp = "tp"
    duplicate = "duplicate"
    fp = "fp"


class SampleOutcome(BaseModel):
    """Matching result for one (case, sample) under one scoring mode."""

    case_id: str
    sample: int
    mode: str  # strict | location
    finding_outcomes: list[FindingOutcome]
    matched_bug_for_finding: list[str | None]  # bug id per finding (tp or duplicate), else None
    detected_bugs: list[str]
    missed_bugs: list[str]


class RunManifest(BaseModel):
    run_id: str
    created_at: str
    aireview_version: str
    git_sha: str | None = None
    git_dirty: bool | None = None
    dataset_version: str
    dataset_hash: str
    split: str
    case_ids: list[str]
    samples: int
    mode: str  # replay | record
    batch: bool = False
    config: ReviewerConfig
    config_hash: str
    prompt_hash: str | None = None
    judge_model: str | None = None
    judge_prompt_version: str | None = None
    tolerance: int = 3
    sample_offset: int = 0  # reviewer request sample index = sample_offset + sample (independent re-records)
    extra: dict[str, Any] = Field(default_factory=dict)
