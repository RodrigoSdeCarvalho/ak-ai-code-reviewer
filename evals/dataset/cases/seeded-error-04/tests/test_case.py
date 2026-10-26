from datetime import datetime, timedelta

from scheduler.jobs import Job, daily_at
from scheduler.runner import Scheduler

T0 = datetime(2026, 5, 4, 2, 0)


class Flaky:
    """Fails the first `failures` calls, then succeeds."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise ConnectionError("warehouse unreachable")


def _nightly(action, retry_delay=timedelta(minutes=5)) -> Job:
    job = daily_at("nightly-export", action, T0, hour=2)
    job.retry_delay = retry_delay
    return job


def test_success_runs_again_after_a_full_interval():
    scheduler = Scheduler()
    job = _nightly(Flaky(0))
    scheduler.add(job)
    [record] = scheduler.tick(T0)
    assert record.ok
    assert job.next_run == T0 + timedelta(days=1)
    assert scheduler.tick(T0 + timedelta(hours=23)) == []


def test_failed_job_is_retried_after_retry_delay_with_backoff():
    scheduler = Scheduler()
    action = Flaky(2)
    job = _nightly(action)
    scheduler.add(job)
    [first] = scheduler.tick(T0)
    assert not first.ok and "warehouse unreachable" in first.error
    assert job.next_run == T0 + timedelta(minutes=5)
    scheduler.tick(T0 + timedelta(minutes=5))
    assert job.next_run == T0 + timedelta(minutes=15)
    [third] = scheduler.tick(T0 + timedelta(minutes=15))
    assert third.ok
    assert job.consecutive_failures == 0
    assert job.next_run == T0 + timedelta(minutes=15, days=1)


def test_backoff_is_capped_at_the_interval():
    scheduler = Scheduler(max_failures=10)
    job = Job("hourly-sync", timedelta(hours=1), Flaky(100), T0, retry_delay=timedelta(minutes=20))
    scheduler.add(job)
    now = T0
    for _ in range(4):
        scheduler.tick(now)
        now = job.next_run
    assert [r.ok for r in scheduler.history] == [False] * 4
    assert job.consecutive_failures == 4
    assert job.next_run == T0 + timedelta(minutes=20 + 40 + 60 + 60)


def test_job_is_disabled_after_max_failures_and_can_be_re_enabled():
    scheduler = Scheduler(max_failures=2)
    action = Flaky(2)
    job = _nightly(action)
    scheduler.add(job)
    scheduler.tick(T0)
    scheduler.tick(job.next_run)
    assert not job.enabled
    assert scheduler.due(T0 + timedelta(days=3)) == []
    scheduler.enable("nightly-export", T0 + timedelta(days=3))
    [record] = scheduler.tick(T0 + timedelta(days=3))
    assert record.ok and action.calls == 3
