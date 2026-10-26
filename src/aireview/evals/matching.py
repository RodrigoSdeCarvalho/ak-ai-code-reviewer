"""Finding-to-bug matching for one (case, sample): location candidates, then a maximum assignment.

Modes: `strict` keeps only candidate pairs the judge called `same`; `location` keeps every candidate.
A finding assigned to a `must_find=false` bug is reported as `duplicate`: it is neither rewarded (tp)
nor penalised (fp), since the label says finding it is optional.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from aireview.diffs import normalize_path
from aireview.evals.schema import Bug, FindingOutcome, SampleOutcome, Verdict
from aireview.models import Finding

MAX_JUDGE_TOL = 10  # the judge is asked about every pair within this distance, so any tol <= it can be scored
MODES = ("strict", "location")

_FORBIDDEN = 1e9
_BASE_WEIGHT = 1000
_MUST_FIND_BONUS = 1000  # prefer claiming a must_find bug over an optional one at the same finding


def finding_span(finding: Finding) -> tuple[int, int]:
    """[line, end_line] of a finding; an end_line before line is treated as absent."""
    end = finding.end_line if finding.end_line is not None and finding.end_line >= finding.line else finding.line
    return finding.line, end


def line_distance(finding: Finding, bug: Bug) -> int:
    """Gap in lines between the finding span and the bug span (0 when they overlap)."""
    lo, hi = finding_span(finding)
    return max(0, bug.line_start - hi, lo - bug.line_end)


def is_candidate(finding: Finding, bug: Bug, tol: int) -> bool:
    """Same file and the finding span overlaps [line_start - tol, line_end + tol]."""
    return normalize_path(finding.file) == normalize_path(bug.file) and line_distance(finding, bug) <= tol


def location_candidates(findings: Sequence[Finding], bugs: Sequence[Bug], tol: int) -> list[tuple[int, str]]:
    """(finding index, bug id) for every location-compatible pair, in finding then bug order."""
    return [(i, b.id) for i, f in enumerate(findings) for b in bugs if is_candidate(f, b, tol)]


def _allowed(
    i: int, bug: Bug, mode: str, candidates: set[tuple[int, str]], verdicts: Mapping[tuple[int, str], Verdict | None]
) -> bool:
    if (i, bug.id) not in candidates:
        return False
    return mode == "location" or verdicts.get((i, bug.id)) == Verdict.same


def match_sample(
    case_id: str,
    sample: int,
    findings: Sequence[Finding],
    bugs: Sequence[Bug],
    verdicts: Mapping[tuple[int, str], Verdict | None],
    mode: str,
    tol: int,
) -> SampleOutcome:
    """Assign findings to bugs (each bug claimed at most once) and label every finding tp / duplicate / fp.

    Cost per allowed edge is -(1000 - line_distance) (plus a bonus for must_find bugs), so the
    assignment maximises matches first and prefers the closest finding on ties. A finding left
    unassigned but with an allowed edge is a duplicate; everything else is a false positive.
    A missing or None verdict never allows an edge in strict mode.
    """
    if mode not in MODES:
        raise ValueError(f"unknown matching mode {mode!r}")
    candidates = set(location_candidates(findings, bugs, tol))
    allowed = np.zeros((len(findings), len(bugs)), dtype=bool)
    cost = np.full((len(findings), len(bugs)), _FORBIDDEN)
    for i, f in enumerate(findings):
        for j, b in enumerate(bugs):
            if _allowed(i, b, mode, candidates, verdicts):
                allowed[i, j] = True
                weight = _BASE_WEIGHT - min(line_distance(f, b), _BASE_WEIGHT - 1)
                cost[i, j] = -(weight + (_MUST_FIND_BONUS if b.must_find else 0))

    assigned: dict[int, int] = {}
    if allowed.any():
        rows, cols = linear_sum_assignment(cost)
        assigned = {int(r): int(c) for r, c in zip(rows, cols, strict=True) if allowed[r, c]}

    outcomes: list[FindingOutcome] = []
    matched: list[str | None] = []
    for i, f in enumerate(findings):
        if i in assigned:
            bug = bugs[assigned[i]]
            outcomes.append(FindingOutcome.tp if bug.must_find else FindingOutcome.duplicate)
            matched.append(bug.id)
        elif allowed[i].any():
            nearest = min(np.flatnonzero(allowed[i]), key=lambda j: line_distance(f, bugs[j]))
            outcomes.append(FindingOutcome.duplicate)
            matched.append(bugs[nearest].id)
        else:
            outcomes.append(FindingOutcome.fp)
            matched.append(None)

    claimed = {bugs[j].id for j in assigned.values()}
    must = [b.id for b in bugs if b.must_find]
    return SampleOutcome(
        case_id=case_id,
        sample=sample,
        mode=mode,
        finding_outcomes=outcomes,
        matched_bug_for_finding=matched,
        detected_bugs=[b for b in must if b in claimed],
        missed_bugs=[b for b in must if b not in claimed],
    )
