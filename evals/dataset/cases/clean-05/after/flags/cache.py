"""Time-bounded cache in front of a flag backend."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from flags.backend import BackendUnavailable, FlagBackend

Clock = Callable[[], float]


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    refresh_errors: int = 0
    stale_served: int = 0

    @property
    def hit_rate(self) -> float:
        lookups = self.hits + self.misses
        return self.hits / lookups if lookups else 0.0


@dataclass(frozen=True)
class _Snapshot:
    flags: dict[str, bool]
    fetched_at: float
    checked_at: float


class CachedBackend:
    """A FlagBackend that keeps each environment's flags for `ttl` seconds.

    One thread at a time refreshes a given environment; the others wait and reuse its result.
    When a refresh raises BackendUnavailable and the previous snapshot is younger than
    `max_stale` seconds, the previous snapshot is served for another `ttl` seconds before the
    backend is tried again.
    """

    def __init__(
        self,
        backend: FlagBackend,
        ttl: float = 30.0,
        max_stale: float = 300.0,
        clock: Clock = time.monotonic,
    ) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_stale < ttl:
            raise ValueError("max_stale must be at least ttl")
        self._backend = backend
        self._ttl = ttl
        self._max_stale = max_stale
        self._clock = clock
        self._guard = threading.Lock()
        self._snapshots: dict[str, _Snapshot] = {}
        self._refresh_locks: dict[str, threading.Lock] = {}
        self._generation = 0
        self.stats = CacheStats()

    def _snapshot(self, environment: str) -> _Snapshot | None:
        with self._guard:
            return self._snapshots.get(environment)

    def _fresh(self, environment: str, now: float) -> _Snapshot | None:
        snapshot = self._snapshot(environment)
        if snapshot is None:
            return None
        if now - snapshot.checked_at < self._ttl and now - snapshot.fetched_at < self._max_stale:
            return snapshot
        return None

    def _store(self, environment: str, snapshot: _Snapshot, generation: int) -> None:
        with self._guard:
            if generation == self._generation:
                self._snapshots[environment] = snapshot

    def _count(self, counter: str) -> None:
        with self._guard:
            setattr(self.stats, counter, getattr(self.stats, counter) + 1)

    def _refresh_lock(self, environment: str) -> threading.Lock:
        with self._guard:
            lock = self._refresh_locks.get(environment)
            if lock is None:
                lock = self._refresh_locks[environment] = threading.Lock()
            return lock

    def fetch(self, environment: str) -> dict[str, bool]:
        """The flags of `environment`, from the cache if the backend was checked less than `ttl` ago."""
        snapshot = self._fresh(environment, self._clock())
        if snapshot is not None:
            self._count("hits")
            return dict(snapshot.flags)
        lock = self._refresh_lock(environment)
        lock.acquire()
        try:
            now = self._clock()
            snapshot = self._fresh(environment, now)
            if snapshot is not None:
                self._count("hits")
                return dict(snapshot.flags)
            self._count("misses")
            with self._guard:
                generation = self._generation
            try:
                flags = dict(self._backend.fetch(environment))
            except BackendUnavailable:
                self._count("refresh_errors")
                previous = self._snapshot(environment)
                if previous is None or now - previous.fetched_at >= self._max_stale:
                    raise
                self._count("stale_served")
                self._store(environment, replace(previous, checked_at=now), generation)
                return dict(previous.flags)
            self._store(environment, _Snapshot(flags, fetched_at=now, checked_at=now), generation)
            return dict(flags)
        finally:
            lock.release()

    def invalidate(self, environment: str | None = None) -> None:
        """Forget one environment's snapshot, or all of them; refreshes already running are not stored."""
        with self._guard:
            self._generation += 1
            if environment is None:
                self._snapshots.clear()
            else:
                self._snapshots.pop(environment, None)
