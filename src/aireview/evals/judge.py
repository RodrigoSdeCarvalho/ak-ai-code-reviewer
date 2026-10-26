"""LLM judge: "do this finding and this labelled bug describe the same defect?" (plus optional FP triage).

Every call goes through an `LLMClient`, so verdicts are cassettes like reviews: replayable offline,
and keyed on the judge prompt version and model. A judge failure is recorded as `verdict=None`,
never as a silent `different`.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from aireview.diffs import normalize_path
from aireview.evals.matching import MAX_JUDGE_TOL, finding_span, location_candidates, nearest_location
from aireview.evals.schema import Bug, Case, Judgment, Verdict
from aireview.llm.base import LLMClient, LLMRequest, LLMResponse
from aireview.models import Finding, Usage
from aireview.settings import DEFAULT_JUDGE_MODEL

# v2 (2026-10-26): a labelled bug may list alternative locations; same_defect_v1.md is kept for reference.
JUDGE_PROMPT_VERSION = "same-defect-v2"
TRIAGE_PROMPT_VERSION = "fp-triage-v1"
PROMPT_DIR = Path(__file__).parent / "judge_prompts"
CONTEXT_LINES = 10
TRIAGE_CONTEXT_LINES = 20
JUDGE_EFFORT = "low"
JUDGE_MAX_TOKENS = 4000

_TAG_RE = re.compile(r"<(/?)(description_a|description_b|comment|code)\b", re.IGNORECASE)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    verdict: Literal["same", "different", "unsure"]


class TriageOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    label: Literal["valid_issue", "nit", "incorrect"]


@dataclass
class JudgeItem:
    case: Case
    case_dir: Path
    sample: int
    finding_index: int
    finding: Finding
    bug: Bug


@dataclass
class TriageItem:
    case: Case
    case_dir: Path
    sample: int
    finding_index: int
    finding: Finding


@cache
def load_judge_prompt(name: str) -> str:
    """System prompt text for a judge prompt version (`same-defect-v1` -> same_defect_v1.md)."""
    return (PROMPT_DIR / f"{name.replace('-', '_')}.md").read_text(encoding="utf-8")


def swap_order(case_id: str, bug_id: str, finding: Finding) -> bool:
    """Deterministic position-bias control: True puts the finding first ("Description A")."""
    text = f"{case_id}|{bug_id}|{finding.title}\n{finding.description}"
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16) % 2 == 1


def candidate_items(
    case: Case, case_dir: Path, sample: int, findings: Sequence[Finding], tol: int = MAX_JUDGE_TOL
) -> list[JudgeItem]:
    """One JudgeItem per location-candidate (finding, bug) pair of a review."""
    bugs = {b.id: b for b in case.bugs}
    return [
        JudgeItem(case, case_dir, sample, i, findings[i], bugs[bug_id])
        for i, bug_id in location_candidates(findings, case.bugs, tol)
    ]


def _as_data(text: str) -> str:
    """Neutralise tags that could close the data wrapper early."""
    return _TAG_RE.sub(lambda m: f"&lt;{m.group(1)}{m.group(2)}", text)


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for lo, hi in sorted(spans):
        if merged and lo <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(hi, merged[-1][1]))
        else:
            merged.append((lo, hi))
    return merged


def code_context(case_dir: Path, spans: Sequence[tuple[str, int, int]], radius: int) -> str:
    """Numbered `after/` code, `radius` lines around each (file, start, end) span, overlapping windows merged."""
    by_file: dict[str, list[tuple[int, int]]] = {}
    for file, start, end in spans:
        by_file.setdefault(normalize_path(file), []).append((max(1, start - radius), end + radius))
    blocks = []
    for file, windows in by_file.items():
        path = case_dir / "after" / file
        if not path.is_file():
            blocks.append(f'<code file="{file}">\n(file not present in the post-change tree)\n</code>')
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lo, hi in _merge(windows):
            body = "\n".join(f"{n:>5} | {lines[n - 1]}" for n in range(lo, min(hi, len(lines)) + 1))
            blocks.append(f'<code file="{file}" lines="{lo}-{min(hi, len(lines))}">\n{_as_data(body)}\n</code>')
    return "\n\n".join(blocks)


def describe_bug(bug: Bug) -> str:
    """The reference text: labelled location, any alternative locations, then the description."""
    head = f"File: {bug.file}, lines {bug.line_start}-{bug.line_end}"
    if bug.alt_locations:
        alts = "; ".join(f"{loc.file}, lines {loc.line_start}-{loc.line_end}" for loc in bug.alt_locations)
        head += f"\nAlso reportable at: {alts}"
    return f"{head}\n{bug.description.strip()}"


def bug_spans(bug: Bug, finding: Finding) -> list[tuple[str, int, int]]:
    """Code spans to show for a (finding, bug) pair: the labelled location and, when it differs, the bug
    location nearest to the finding, so a finding at an alternative location is judged next to its code."""
    spans = [(bug.file, bug.line_start, bug.line_end)]
    near = nearest_location(finding, bug)
    if near != bug.primary:
        spans.append((near.file, near.line_start, near.line_end))
    return spans


def describe_finding(finding: Finding) -> str:
    start, end = finding_span(finding)
    return f"File: {finding.file}, lines {start}-{end}\n{finding.title.strip()}\n{finding.description.strip()}"


def parse_output[T: BaseModel](response: LLMResponse, model: type[T]) -> tuple[T | None, str | None]:
    """Strictly validate the judge's JSON; returns (output, None) or (None, error)."""
    if response.error:
        return None, f"{response.error_class or 'error'}: {response.error}"
    data: Any = response.parsed
    if data is None and response.raw_text:
        try:
            data = json.loads(response.raw_text)
        except json.JSONDecodeError:
            data = None
    if data is None:
        return None, "judge_parse_error: no JSON object in the response"
    try:
        return model.model_validate(data), None
    except ValidationError as exc:
        return None, f"judge_parse_error: {exc.errors()[0]['msg']}"


class Judge:
    """Same-defect judge (and FP triage) over an `LLMClient`.

    Identical requests are sent once per Judge lifetime (one run), not just once per call, so a pair that
    repeats across chunks gets one verdict and is paid for once.
    """

    prompt_version = JUDGE_PROMPT_VERSION

    def __init__(self, client: LLMClient, model: str = DEFAULT_JUDGE_MODEL) -> None:
        self.client = client
        self.model = model
        self._memo: dict[str, LLMResponse] = {}
        self._charged: set[str] = set()

    def _request(self, system: str, user: str, schema: type[BaseModel], version: str) -> LLMRequest:
        return LLMRequest(
            role="judge",
            model=self.model,
            system=system,
            user=user,
            output_schema=schema.model_json_schema(),
            max_tokens=JUDGE_MAX_TOKENS,
            effort=JUDGE_EFFORT,
            sample=0,
            prompt_version=version,
        )

    def build_request(self, item: JudgeItem) -> tuple[LLMRequest, bool]:
        """The judge request for one pair and whether the finding was shown as Description A."""
        swapped = swap_order(item.case.id, item.bug.id, item.finding)
        start, end = finding_span(item.finding)
        code = code_context(
            item.case_dir, [*bug_spans(item.bug, item.finding), (item.finding.file, start, end)], CONTEXT_LINES
        )
        first, second = describe_bug(item.bug), describe_finding(item.finding)
        if swapped:
            first, second = second, first
        user = (
            f"{code}\n\n<description_a>\n{_as_data(first)}\n</description_a>\n\n"
            f"<description_b>\n{_as_data(second)}\n</description_b>\n\n"
            "Do Description A and Description B describe the same underlying defect?"
        )
        system = load_judge_prompt(JUDGE_PROMPT_VERSION)
        return self._request(system, user, JudgeOutput, JUDGE_PROMPT_VERSION), swapped

    def build_triage_request(self, item: TriageItem) -> LLMRequest:
        start, end = finding_span(item.finding)
        code = code_context(item.case_dir, [(item.finding.file, start, end)], TRIAGE_CONTEXT_LINES)
        user = (
            f"{code}\n\n<comment>\n{_as_data(describe_finding(item.finding))}\n</comment>\n\n"
            "Is this review comment a valid issue, a nit, or incorrect?"
        )
        system = load_judge_prompt(TRIAGE_PROMPT_VERSION)
        return self._request(system, user, TriageOutput, TRIAGE_PROMPT_VERSION)

    def _complete_unique(self, requests: list[LLMRequest]) -> list[tuple[LLMResponse, bool]]:
        """Responses in request order, each with True on the first occurrence of its key in this Judge's life."""
        todo: dict[str, LLMRequest] = {}
        for request in requests:
            key = request.key()
            if key not in self._memo:
                todo.setdefault(key, request)
        if todo:
            self._memo.update(zip(todo, self.client.complete_many(list(todo.values())), strict=True))
        out = []
        for request in requests:
            key = request.key()
            out.append((self._memo[key], key not in self._charged))
            self._charged.add(key)
        return out

    def judge_many(self, items: Sequence[JudgeItem]) -> list[Judgment]:
        """One Judgment per item, in order. Repeated identical pairs carry their cost only once."""
        built = [self.build_request(item) for item in items]
        responses = self._complete_unique([request for request, _ in built])
        judgments = []
        for item, (request, swapped), (response, first) in zip(items, built, responses, strict=True):
            output, error = parse_output(response, JudgeOutput)
            judgments.append(
                Judgment(
                    case_id=item.case.id,
                    sample=item.sample,
                    finding_index=item.finding_index,
                    bug_id=item.bug.id,
                    verdict=Verdict(output.verdict) if output else None,
                    reason=output.reason if output else None,
                    swapped=swapped,
                    usage=response.usage if first else Usage(),
                    cassette_key=request.key(),
                    attempts=response.attempts,
                    error=error,
                )
            )
        return judgments

    def triage_many(self, items: Sequence[TriageItem]) -> list[dict[str, Any]]:
        """Advisory label (valid_issue | nit | incorrect) per unmatched finding; label None on judge error."""
        requests = [self.build_triage_request(item) for item in items]
        rows = []
        for item, request, (response, first) in zip(items, requests, self._complete_unique(requests), strict=True):
            output, error = parse_output(response, TriageOutput)
            rows.append(
                {
                    "case_id": item.case.id,
                    "sample": item.sample,
                    "finding_index": item.finding_index,
                    "label": output.label if output else None,
                    "reason": output.reason if output else None,
                    "error": error,
                    "cost_usd": response.usage.cost_usd if first else 0.0,
                    "cassette_key": request.key(),
                }
            )
        return rows
