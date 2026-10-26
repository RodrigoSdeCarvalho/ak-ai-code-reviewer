import threading

import pytest

import flags.client as client_mod
from flags.backend import BackendUnavailable, InMemoryBackend
from flags.cache import CachedBackend
from flags.client import DEFAULT_FLAGS, FlagClient, client_for, describe


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FlakyBackend(InMemoryBackend):
    def __init__(self, flags):
        super().__init__(flags)
        self.down = False

    def fetch(self, environment):
        if self.down:
            self.fetches += 1
            raise BackendUnavailable("store offline")
        return super().fetch(environment)


def test_snapshot_is_reused_within_ttl_and_refreshed_after():
    backend, clock = InMemoryBackend({"prod": {"checkout_v2": True}}), Clock()
    cache = CachedBackend(backend, ttl=30, max_stale=300, clock=clock)
    assert cache.fetch("prod") == {"checkout_v2": True}
    backend.set("prod", "checkout_v2", False)
    clock.now += 29.9
    assert cache.fetch("prod") == {"checkout_v2": True}
    clock.now += 0.1
    assert cache.fetch("prod") == {"checkout_v2": False}
    assert backend.fetches == 2
    assert (cache.stats.hits, cache.stats.misses) == (1, 2)


def test_callers_cannot_mutate_the_cached_snapshot():
    cache = CachedBackend(InMemoryBackend({"prod": {"a": True}}), clock=Clock())
    cache.fetch("prod")["a"] = False
    assert cache.fetch("prod") == {"a": True}


def test_stale_snapshot_is_served_during_an_outage_with_backoff():
    backend, clock = FlakyBackend({"prod": {"a": True}}), Clock()
    cache = CachedBackend(backend, ttl=10, max_stale=60, clock=clock)
    cache.fetch("prod")
    backend.down = True
    clock.now += 15
    assert cache.fetch("prod") == {"a": True}
    attempts = backend.fetches
    clock.now += 5
    assert cache.fetch("prod") == {"a": True}
    assert backend.fetches == attempts
    clock.now += 41
    with pytest.raises(BackendUnavailable):
        cache.fetch("prod")
    assert cache.stats.stale_served == 1
    assert cache.stats.refresh_errors == 2


def test_outage_without_a_snapshot_raises():
    backend = FlakyBackend({})
    backend.down = True
    with pytest.raises(BackendUnavailable):
        CachedBackend(backend, clock=Clock()).fetch("prod")


def test_invalidate_forces_a_reload():
    backend, clock = InMemoryBackend({"prod": {"a": True}, "dev": {"a": True}}), Clock()
    cache = CachedBackend(backend, clock=clock)
    cache.fetch("prod")
    cache.fetch("dev")
    backend.set("prod", "a", False)
    backend.set("dev", "a", False)
    cache.invalidate("prod")
    assert cache.fetch("prod") == {"a": False}
    assert cache.fetch("dev") == {"a": True}
    cache.invalidate()
    assert cache.fetch("dev") == {"a": False}


def test_concurrent_misses_share_one_backend_fetch():
    gate = threading.Event()

    class SlowBackend(InMemoryBackend):
        def fetch(self, environment):
            gate.wait(2)
            return super().fetch(environment)

    backend = SlowBackend({"prod": {"a": True}})
    cache = CachedBackend(backend, clock=Clock())
    barrier = threading.Barrier(6)
    results = []

    def worker():
        barrier.wait()
        results.append(cache.fetch("prod"))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    gate.set()
    for t in threads:
        t.join()
    assert results == [{"a": True}] * 6
    assert backend.fetches == 1


def test_lock_is_released_after_an_error():
    backend = FlakyBackend({})
    backend.down = True
    cache = CachedBackend(backend, clock=Clock())
    for _ in range(3):
        with pytest.raises(BackendUnavailable):
            cache.fetch("prod")
    backend.down = False
    assert cache.fetch("prod") == {}


def test_defaults_apply_only_where_the_backend_is_silent():
    client = client_for(InMemoryBackend({"prod": {"checkout_v2": True, "invoice_pdf_export": False}}), " PROD ")
    assert client.is_enabled("checkout_v2")
    assert not client.is_enabled("invoice_pdf_export")
    assert client.is_enabled("search_suggestions")
    assert not client.is_enabled("unknown_flag")
    assert client.enabled_flags() == ["checkout_v2", "search_suggestions"]


def test_default_table_is_never_modified():
    original = dict(DEFAULT_FLAGS)
    client = FlagClient(InMemoryBackend({"prod": {"bulk_refunds": True, "extra": True}}), "prod")
    snap = client.snapshot()
    snap["checkout_v2"] = True
    client.enabled_flags()
    assert client_mod.DEFAULT_FLAGS == original


def test_describe_with_stats():
    cache = client_mod.cached(InMemoryBackend({"prod": {}}))
    client = FlagClient(cache, "prod")
    client.is_enabled("checkout_v2")
    assert describe(client, cache.stats) == "prod: 2 enabled (invoice_pdf_export, search_suggestions); cache hit rate 50%, 0 stale"
