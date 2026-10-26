"""In-process periodic job scheduler driven by an external tick."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from scheduler.jobs import Job

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunRecord:
    job: str
    started_at: datetime
    ok: bool
    error: str | None = None


DEFAULT_MAX_FAILURES = 5


class Scheduler:
    def __init__(self, max_history: int = 1000, max_failures: int = DEFAULT_MAX_FAILURES) -> None:
        if max_failures < 1:
            raise ValueError("max_failures must be >= 1")
        self._jobs: dict[str, Job] = {}
        self._max_failures = max_failures
        self.history: deque[RunRecord] = deque(maxlen=max_history)

    def add(self, job: Job) -> None:
        if job.name in self._jobs:
            raise ValueError(f"job {job.name!r} already registered")
        self._jobs[job.name] = job

    def get(self, name: str) -> Job:
        return self._jobs[name]

    def enable(self, name: str, now: datetime) -> None:
        """Re-enable a job disabled after repeated failures and run it at the next tick."""
        job = self._jobs[name]
        job.enabled = True
        job.consecutive_failures = 0
        job.next_run = now

    def due(self, now: datetime) -> list[Job]:
        """Enabled jobs whose next run is at or before `now`, oldest first."""
        ready = [job for job in self._jobs.values() if job.enabled and job.next_run <= now]
        return sorted(ready, key=lambda job: job.next_run)

    def tick(self, now: datetime) -> list[RunRecord]:
        """Run every due job once."""
        return [self._run(job, now) for job in self.due(now)]

    def _run(self, job: Job, now: datetime) -> RunRecord:
        try:
            job.action()
        except Exception as exc:
            logger.exception("job %s failed", job.name)
            job.consecutive_failures += 1
            job.last_error = repr(exc)
            job.next_run = now + self._retry_delay(job)
            if job.consecutive_failures >= self._max_failures:
                logger.error("disabling job %s after %d failures", job.name, job.consecutive_failures)
                job.enabled = False
            record = RunRecord(job.name, now, ok=False, error=job.last_error)
        else:
            job.consecutive_failures = 0
            job.last_success = now
            job.last_error = None
            record = RunRecord(job.name, now, ok=True)
        finally:
            job.next_run = now + job.interval
        self.history.append(record)
        return record

    def _retry_delay(self, job: Job) -> timedelta:
        backoff = job.retry_delay * 2 ** (job.consecutive_failures - 1)
        return min(backoff, job.interval)
