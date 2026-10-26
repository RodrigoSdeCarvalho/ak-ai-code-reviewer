"""A thread-safe, size-bounded in-process cache with per-entry expiry."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from dataclasses import dataclass, replace
from typing import Any

MISSING: Any = object()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    evictions: int = 0


class TTLCache:
    """Values expire `ttl` seconds after they are stored; beyond `max_entries` the least recently used go first."""

    def __init__(self, ttl: float, max_entries: int = 1024, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._ttl = ttl
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._generation = 0
        self._stats = CacheStats()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def stats(self) -> CacheStats:
        with self._lock:
            return replace(self._stats)

    def get(self, key: Hashable) -> Any:
        """The cached value, or MISSING if there is none or it has expired."""
        with self._lock:
            return self._lookup(key)

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            self._store(key, value)

    def get_or_load[T](self, key: Hashable, loader: Callable[[], T]) -> T:
        """The cached value, or the loader's result, which is then cached.

        The loader runs without the lock held; its result is not stored if any invalidation happened meanwhile.
        """
        with self._lock:
            value = self._lookup(key)
            if value is not MISSING:
                return value
            generation = self._generation
        value = loader()
        with self._lock:
            if self._generation == generation:
                self._store(key, value)
        return value

    def invalidate(self, *keys: Hashable) -> None:
        with self._lock:
            self._generation += 1
            for key in keys:
                self._entries.pop(key, None)

    def invalidate_where(self, predicate: Callable[[Hashable], bool]) -> int:
        """Drop every entry whose key the predicate accepts. Returns how many were dropped."""
        with self._lock:
            self._generation += 1
            doomed = [key for key in self._entries if predicate(key)]
            for key in doomed:
                del self._entries[key]
            return len(doomed)

    def purge_expired(self) -> int:
        """Drop expired entries now rather than on their next lookup. Returns how many were dropped."""
        with self._lock:
            now = self._clock()
            expired = [key for key, (expires_at, _) in self._entries.items() if expires_at <= now]
            for key in expired:
                del self._entries[key]
            return len(expired)

    def _lookup(self, key: Hashable) -> Any:
        entry = self._entries.get(key)
        if entry is not None and entry[0] > self._clock():
            self._entries.move_to_end(key)
            self._stats.hits += 1
            return entry[1]
        if entry is not None:
            del self._entries[key]
        self._stats.misses += 1
        return MISSING

    def _store(self, key: Hashable, value: Any) -> None:
        self._entries[key] = (self._clock() + self._ttl, value)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
            self._stats.evictions += 1
