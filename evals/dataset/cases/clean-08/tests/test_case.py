from datetime import UTC, datetime, timedelta

import pytest

from telemetry.pipeline import SessionReport, run_daily_job, run_session_job
from telemetry.readings import Reading
from telemetry.sessions import sessionize


def _reading(device: str, minute: int, celsius: float = 20.0) -> Reading:
    return Reading(device, datetime(2026, 3, 1, 8, 0, tzinfo=UTC) + timedelta(minutes=minute), celsius)


def test_gap_longer_than_max_starts_a_new_session():
    readings = [_reading("a", m) for m in (0, 5, 10, 26, 30)]
    sessions = list(sessionize(readings, timedelta(minutes=15)))
    assert [(s.samples, s.duration) for s in sessions] == [(3, timedelta(minutes=10)), (2, timedelta(minutes=4))]


def test_gap_of_exactly_max_gap_stays_in_the_session():
    sessions = list(sessionize([_reading("a", 0), _reading("a", 15), _reading("a", 30)], timedelta(minutes=15)))
    assert len(sessions) == 1
    assert sessions[0].samples == 3


def test_unordered_input_from_several_devices():
    readings = [_reading("b", 40, 3.0), _reading("a", 10, 7.5), _reading("b", 0, 1.0), _reading("a", 0, 9.0)]
    sessions = list(sessionize(readings))
    assert [(s.device_id, s.samples) for s in sessions] == [("a", 2), ("b", 1), ("b", 1)]
    assert (sessions[0].min_celsius, sessions[0].max_celsius) == (7.5, 9.0)
    assert sessions[1].started_at < sessions[2].started_at


def test_single_reading_is_a_zero_length_session():
    (session,) = sessionize([_reading("a", 3)])
    assert session.duration == timedelta(0)


def test_empty_input_yields_nothing():
    assert list(sessionize([])) == []


@pytest.mark.parametrize("gap", [timedelta(0), timedelta(minutes=-1)])
def test_non_positive_gap_is_rejected(gap):
    with pytest.raises(ValueError):
        list(sessionize([_reading("a", 0)], gap))


LINES = [
    "# exported 2026-03-01",
    "a,2026-03-01T08:00:00+00:00,20.0",
    "a,2026-03-01T08:10:00+00:00,21.0",
    "a,2026-03-01T09:00:00+00:00,22.0",
    "a,2026-03-01T09:30:00+00:00,999",
    "b,2026-03-01T08:00:00,18.0",
    "b,not-a-time,18.0",
    "",
    "b,2026-03-01T08:05:00,nan",
]


def test_session_job_reports_per_device_and_collects_errors():
    reports, errors = run_session_job(LINES)
    assert reports == [
        SessionReport("a", sessions=2, longest=timedelta(minutes=10), samples=3),
        SessionReport("b", sessions=1, longest=timedelta(0), samples=1),
    ]
    assert len(errors) == 1
    assert "not-a-time" in errors[0]


def test_daily_job_unchanged():
    results, errors = run_daily_job(LINES)
    assert [(r.device_id, r.celsius, r.samples) for r in results] == [("a", 21.0, 3), ("b", 18.0, 1)]
    assert len(errors) == 1
