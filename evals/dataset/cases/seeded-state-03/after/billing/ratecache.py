"""Time-bounded LRU cache for tax rates with per-country invalidation."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

Key = tuple[str, str]
Loader = Callable[[str, str], Decimal]
Clock = Callable[[], datetime]


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CacheStats:
    hits: int
    misses: int
    evictions: int
    size: int

    @property
    def hit_ratio(self) -> float:
        lookups = self.hits + self.misses
        return self.hits / lookups if lookups else 0.0


@dataclass(frozen=True)
class _Entry:
    rate: Decimal
    expires_at: datetime


class RateCache:
    """Caches `loader(country, postal_code)` for `ttl`, keeping at most `max_entries` rates.

    The loader runs while the cache lock is held, so a lookup never stores a rate that an
    invalidation has already superseded.
    """

    def __init__(
        self,
        loader: Loader,
        *,
        ttl: timedelta = timedelta(hours=1),
        max_entries: int = 4096,
        clock: Clock = utcnow,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._loader = loader
        self._ttl = ttl
        self._max_entries = max_entries
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: OrderedDict[Key, _Entry] = OrderedDict()
        self._keys_by_country: dict[str, set[Key]] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def get(self, country: str, postal_code: str) -> Decimal:
        key = (country, postal_code)
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and entry.expires_at > now:
                self._entries.move_to_end(key)
                self._hits += 1
                return entry.rate
            self._misses += 1
            rate = self._loader(country, postal_code)
            self._store(key, _Entry(rate, now + self._ttl))
            return rate

    def invalidate_country(self, country: str) -> int:
        """Drop every cached rate for `country`; returns how many were dropped."""
        with self._lock:
            keys = self._keys_by_country.pop(country, set())
            for key in keys:
                del self._entries[key]
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._keys_by_country.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(self._hits, self._misses, self._evictions, len(self._entries))

    def _store(self, key: Key, entry: _Entry) -> None:
        self._entries[key] = entry
        self._entries.move_to_end(key)
        self._keys_by_country.setdefault(key[0], set()).add(key)
        while len(self._keys_by_country) > self._max_entries:
            self._evict_oldest()

    def _evict_oldest(self) -> None:
        key, _ = self._entries.popitem(last=False)
        keys = self._keys_by_country[key[0]]
        keys.discard(key)
        if not keys:
            del self._keys_by_country[key[0]]
        self._evictions += 1
