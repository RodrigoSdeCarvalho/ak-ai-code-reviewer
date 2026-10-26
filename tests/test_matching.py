from aireview.evals.matching import MAX_JUDGE_TOL, is_candidate, line_distance, location_candidates, match_sample
from aireview.evals.schema import Bug, FindingOutcome, Verdict
from aireview.models import Category, Finding, Severity


def bug(bug_id="b1", line_start=10, line_end=12, file="app/x.py", must_find=True):
    return Bug(
        id=bug_id,
        file=file,
        line_start=line_start,
        line_end=line_end,
        severity=Severity.high,
        category=Category.logic,
        description="d",
        must_find=must_find,
    )


def finding(line, end_line=None, file="app/x.py", title="t"):
    return Finding(
        file=file,
        line=line,
        end_line=end_line,
        severity=Severity.high,
        category=Category.logic,
        title=title,
        description="d",
        confidence=0.5,
    )


def test_tolerance_edges():
    b = bug(line_start=10, line_end=12)
    assert is_candidate(finding(7), b, 3)
    assert not is_candidate(finding(6), b, 3)
    assert is_candidate(finding(15), b, 3)
    assert not is_candidate(finding(16), b, 3)
    assert is_candidate(finding(1, end_line=7), b, 3)
    assert is_candidate(finding(11), b, 0)
    assert not is_candidate(finding(9), b, 0)
    assert line_distance(finding(20, end_line=25), b) == 8


def test_paths_are_normalized_and_files_must_match():
    b = bug()
    assert is_candidate(finding(10, file="./app/x.py"), b, 0)
    assert is_candidate(finding(10, file="b/app/x.py"), b, 0)
    assert is_candidate(finding(10, file="app\\x.py"), b, 0)
    assert not is_candidate(finding(10, file="app/y.py"), b, 3)


def test_location_candidates_order():
    bugs = [bug("b1", 10, 10), bug("b2", 30, 30)]
    findings = [finding(31), finding(11), finding(100)]
    assert location_candidates(findings, bugs, 3) == [(0, "b2"), (1, "b1")]
    assert MAX_JUDGE_TOL == 10


def test_hungarian_prefers_closest_and_marks_duplicate():
    out = match_sample("c", 0, [finding(14), finding(10)], [bug()], {}, "location", 3)
    assert out.finding_outcomes == [FindingOutcome.duplicate, FindingOutcome.tp]
    assert out.matched_bug_for_finding == ["b1", "b1"]
    assert out.detected_bugs == ["b1"] and out.missed_bugs == []


def test_assignment_maximises_matches_over_greedy_closeness():
    bugs = [bug("b1", 10, 10), bug("b2", 12, 12)]
    # f0 is closest to b1 but is the only finding that can reach b2.
    findings = [finding(10), finding(8)]
    out = match_sample("c", 0, findings, bugs, {}, "location", 2)
    assert sorted(out.detected_bugs) == ["b1", "b2"]
    assert out.matched_bug_for_finding == ["b2", "b1"]


def test_strict_needs_same_verdict():
    findings = [finding(10), finding(11), finding(12), finding(13)]
    verdicts = {(0, "b1"): Verdict.different, (1, "b1"): Verdict.unsure, (2, "b1"): None}
    out = match_sample("c", 0, findings, [bug()], verdicts, "strict", 3)
    assert out.finding_outcomes == [FindingOutcome.fp] * 4
    assert out.missed_bugs == ["b1"]
    verdicts[(3, "b1")] = Verdict.same
    out = match_sample("c", 0, findings, [bug()], verdicts, "strict", 3)
    assert out.finding_outcomes[3] == FindingOutcome.tp
    assert out.detected_bugs == ["b1"]


def test_strict_same_verdict_outside_tolerance_is_not_a_match():
    out = match_sample("c", 0, [finding(20)], [bug()], {(0, "b1"): Verdict.same}, "strict", 3)
    assert out.finding_outcomes == [FindingOutcome.fp]


def test_must_find_false_bug_is_neither_tp_nor_fp():
    bugs = [bug("b1", 10, 10), bug("opt", 40, 40, must_find=False)]
    out = match_sample("c", 0, [finding(40)], bugs, {}, "location", 3)
    assert out.finding_outcomes == [FindingOutcome.duplicate]
    assert out.matched_bug_for_finding == ["opt"]
    assert out.detected_bugs == [] and out.missed_bugs == ["b1"]


def test_must_find_bug_wins_over_closer_optional_bug():
    bugs = [bug("opt", 10, 10, must_find=False), bug("b1", 12, 12)]
    out = match_sample("c", 0, [finding(10)], bugs, {}, "location", 3)
    assert out.finding_outcomes == [FindingOutcome.tp]
    assert out.detected_bugs == ["b1"]


def test_no_findings_and_no_bugs():
    assert match_sample("c", 0, [], [bug()], {}, "strict", 3).missed_bugs == ["b1"]
    out = match_sample("c", 0, [finding(3)], [], {}, "strict", 3)
    assert out.finding_outcomes == [FindingOutcome.fp]
