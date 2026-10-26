from datetime import datetime, timedelta

import pytest

from scheduler.jobs import Job, JobStatus, Scheduler, SchedulerBusy

T0 = datetime(2026, 7, 1, 8, 0)


def _scheduler() -> Scheduler:
    sched = Scheduler(lock_timeout=0.05)
    sched.add(Job("a", "send-digest", T0))
    sched.add(Job("b", "rebuild-index", T0 + timedelta(minutes=5)))
    return sched


def _lock_is_free(sched: Scheduler) -> bool:
    try:
        sched.get("a")
    except SchedulerBusy:
        return False
    return True


def test_rejected_reschedule_of_unknown_job_releases_the_lock():
    sched = _scheduler()
    assert sched.reschedule("missing", T0) is False
    assert _lock_is_free(sched)


def test_rejected_reschedule_of_running_job_releases_the_lock():
    sched = _scheduler()
    assert [job.job_id for job in sched.claim_due(T0)] == ["a"]
    assert sched.reschedule("a", T0 + timedelta(hours=1)) is False
    assert _lock_is_free(sched)
    assert sched.claim_due(T0 + timedelta(minutes=5))[0].job_id == "b"


def test_reschedule_and_retry_happy_paths():
    sched = _scheduler()
    assert sched.reschedule("b", T0 - timedelta(minutes=1)) is True
    assert [job.job_id for job in sched.claim_due(T0)] == ["b", "a"]
    sched.finish("a", ok=False)
    assert sched.retry("a", T0 + timedelta(minutes=10)) is True
    assert sched.get("a").status is JobStatus.PENDING
    assert sched.retry("b", T0) is False
    assert sched.retry("missing", T0) is False
    with pytest.raises(ValueError):
        sched.add(Job("a", "dup", T0))
