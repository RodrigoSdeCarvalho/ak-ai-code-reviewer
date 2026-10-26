"""Known-good and known-bad reviewers that need no model: oracle, null and spam (the scorer's sanity checks).

They are judged by `ExactMatchJudge`, a deterministic stand-in for the LLM judge: a finding is the
`same` defect as a bug only when its description is the bug's description verbatim. So the oracle
scores recall = precision = 1 in both modes, and spam (generic text on every changed line) scores
recall ~1 in location mode and ~0 in strict mode, at zero cost and fully offline.
"""

from __future__ import annotations

from collections.abc import Sequence

from aireview import __version__
from aireview.diffs import parse_unified_diff
from aireview.evals.judge import JudgeItem
from aireview.evals.schema import Case, Judgment, Verdict
from aireview.models import Category, Finding, Review, ReviewerInfo, Severity

SYNTHETIC_BACKENDS = ("oracle", "null", "spam")
EXACT_JUDGE_MODEL = "exact-match"
EXACT_JUDGE_PROMPT_VERSION = "exact-match-v1"
SPAM_TITLE = "Review this changed line"
SPAM_DESCRIPTION = "This line changed; it may contain a defect."


def _info(backend: str) -> ReviewerInfo:
    return ReviewerInfo(version=__version__, backend=backend)


def _title(description: str) -> str:
    first = description.strip().splitlines()[0] if description.strip() else "Labelled defect"
    return first if len(first) <= 100 else first[:97] + "..."


def oracle_review(case: Case) -> Review:
    """The gold must_find bugs as findings, with their own location, severity, category and description."""
    findings = [
        Finding(
            file=bug.file,
            line=bug.line_start,
            end_line=bug.line_end,
            severity=bug.severity,
            category=bug.category,
            title=_title(bug.description),
            description=bug.description,
            confidence=1.0,
        )
        for bug in case.bugs
        if bug.must_find
    ]
    return Review(reviewer=_info("oracle"), findings=findings)


def null_review() -> Review:
    """No findings."""
    return Review(reviewer=_info("null"))


def spam_review(diff_text: str) -> Review:
    """One low-severity maintainability finding on every changed line of every surviving file."""
    findings = [
        Finding(
            file=fd.path,
            line=line,
            severity=Severity.low,
            category=Category.maintainability,
            title=SPAM_TITLE,
            description=SPAM_DESCRIPTION,
            confidence=0.1,
        )
        for fd in parse_unified_diff(diff_text)
        if not fd.is_deleted
        for line in sorted(fd.changed_lines)
    ]
    return Review(reviewer=_info("spam"), findings=findings)


def synthetic_review(backend: str, case: Case, diff_text: str) -> Review:
    """Dispatch on a synthetic backend name."""
    if backend == "oracle":
        return oracle_review(case)
    if backend == "null":
        return null_review()
    if backend == "spam":
        return spam_review(diff_text)
    raise ValueError(f"{backend!r} is not a synthetic backend; expected one of {SYNTHETIC_BACKENDS}")


class ExactMatchJudge:
    """Judge for synthetic runs: `same` iff the finding's description equals the bug's description."""

    model = EXACT_JUDGE_MODEL
    prompt_version = EXACT_JUDGE_PROMPT_VERSION

    def judge_many(self, items: Sequence[JudgeItem]) -> list[Judgment]:
        out = []
        for item in items:
            same = item.finding.description.strip() == item.bug.description.strip()
            out.append(
                Judgment(
                    case_id=item.case.id,
                    sample=item.sample,
                    finding_index=item.finding_index,
                    bug_id=item.bug.id,
                    verdict=Verdict.same if same else Verdict.different,
                    reason="description identical to the label" if same else "description differs from the label",
                )
            )
        return out
