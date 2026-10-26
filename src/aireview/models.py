"""Shared data contract: what the reviewer emits and what the eval reads."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"


class Severity(StrEnum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


SEVERITY_RANK = {Severity.low: 0, Severity.medium: 1, Severity.high: 2, Severity.critical: 3}


class Category(StrEnum):
    logic = "logic"
    security = "security"
    error_handling = "error_handling"
    concurrency = "concurrency"
    resource = "resource"
    performance = "performance"
    api_contract = "api_contract"
    maintainability = "maintainability"


class ReviewStatus(StrEnum):
    """Outcome of one review call. Anything but `ok` is a serving outcome, never "no findings"."""

    ok = "ok"
    truncated = "truncated"
    refused = "refused"
    schema_error = "schema_error"
    api_error = "api_error"


class Finding(BaseModel):
    """One review comment. `line` is 1-based in the post-change file."""

    model_config = ConfigDict(extra="forbid")

    file: str = Field(
        description="Repo-relative path with forward slashes, as it appears in the diff (no a/ or b/ prefix)."
    )
    line: int = Field(ge=1, description="1-based line number in the post-change version of the file.")
    end_line: int | None = Field(default=None, ge=1, description="Last line of the issue, if it spans several lines.")
    severity: Severity
    category: Category
    title: str = Field(description="One-line summary of the defect.")
    description: str = Field(description="What is wrong, and what goes wrong at runtime because of it.")
    suggestion: str | None = Field(default=None, description="A concrete fix, if one is clear.")
    confidence: float = Field(ge=0, le=1, description="How sure the reviewer is that this is a real defect.")


class ReviewOutput(BaseModel):
    """The structured-output schema the model fills in."""

    model_config = ConfigDict(extra="forbid")

    findings: list[Finding]


class Usage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int | None = None  # None when not measured (batch, replay of a batch row)

    def __add__(self, other: Usage) -> Usage:
        latency = None
        if self.latency_ms is not None or other.latency_ms is not None:
            latency = (self.latency_ms or 0) + (other.latency_ms or 0)
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_input_tokens=self.cache_read_input_tokens + other.cache_read_input_tokens,
            cache_creation_input_tokens=self.cache_creation_input_tokens + other.cache_creation_input_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            latency_ms=latency,
        )


class ReviewerInfo(BaseModel):
    name: str = "aireview"
    version: str
    prompt_version: str | None = None
    model: str | None = None
    backend: str


class Review(BaseModel):
    """The reviewer's output file (`findings.json`)."""

    schema_version: str = SCHEMA_VERSION
    reviewer: ReviewerInfo
    status: ReviewStatus = ReviewStatus.ok
    findings: list[Finding] = Field(default_factory=list)
    out_of_scope_findings: list[Finding] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None
