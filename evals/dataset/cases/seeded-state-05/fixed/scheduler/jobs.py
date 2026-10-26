"""In-process job scheduler polled by worker threads."""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum


class SchedulerBusy(RuntimeError):
    """Raised when the scheduler lock cannot be taken within the configured timeout."""


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class Job:
    job_id: str
    name: str
    run_at: datetime
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0


class Scheduler:
    def __init__(self, lock_timeout: float = 5.0) -> None:
        self._lock = threading.Lock()
        self._lock_timeout = lock_timeout
        self._jobs: dict[str, Job] = {}

    def _acquire(self) -> None:
        if not self._lock.acquire(timeout=self._lock_timeout):
            raise SchedulerBusy(f"scheduler lock not acquired within {self._lock_timeout}s")

    def add(self, job: Job) -> None:
        self._acquire()
        try:
            if job.job_id in self._jobs:
                raise ValueError(f"duplicate job id {job.job_id}")
            self._jobs[job.job_id] = job
        finally:
            self._lock.release()

    def claim_due(self, now: datetime, limit: int = 10) -> list[Job]:
        """Mark up to `limit` pending jobs whose time has come as running and return them."""
        self._acquire()
        try:
            due = sorted(
                (j for j in self._jobs.values() if j.status is JobStatus.PENDING and j.run_at <= now),
                key=lambda j: j.run_at,
            )[:limit]
            for job in due:
                self._jobs[job.job_id] = replace(job, status=JobStatus.RUNNING, attempts=job.attempts + 1)
            return [self._jobs[job.job_id] for job in due]
        finally:
            self._lock.release()

    def finish(self, job_id: str, ok: bool) -> None:
        self._acquire()
        try:
            job = self._jobs[job_id]
            self._jobs[job_id] = replace(job, status=JobStatus.DONE if ok else JobStatus.FAILED)
        finally:
            self._lock.release()

    def reschedule(self, job_id: str, run_at: datetime) -> bool:
        """Move a pending job to `run_at`. False if the job is unknown or has already started."""
        self._acquire()
        try:
            job = self._jobs.get(job_id)
            if job is None or job.status is not JobStatus.PENDING:
                return False
            self._jobs[job_id] = replace(job, run_at=run_at)
            return True
        finally:
            self._lock.release()

    def retry(self, job_id: str, run_at: datetime, max_attempts: int = 3) -> bool:
        """Queue a failed job again at `run_at`. False if unknown, not failed or out of attempts."""
        self._acquire()
        try:
            job = self._jobs.get(job_id)
            if job is None or job.status is not JobStatus.FAILED or job.attempts >= max_attempts:
                return False
            self._jobs[job_id] = replace(job, status=JobStatus.PENDING, run_at=run_at)
            return True
        finally:
            self._lock.release()

    def get(self, job_id: str) -> Job | None:
        self._acquire()
        try:
            return self._jobs.get(job_id)
        finally:
            self._lock.release()
