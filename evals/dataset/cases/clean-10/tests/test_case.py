import pytest

from catalog.cache import MISSING, TTLCache
from catalog.repository import Product, ProductRepository
from catalog.service import CatalogService, UnknownProduct


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def repo():
    repository = ProductRepository()
    repository.save_many(
        [
            Product("MUG-1", "Mug", "kitchen", 900),
            Product("MUG-2", "Big mug", "kitchen", 1200),
            Product("LAMP-1", "Lamp", "lighting", 4500),
        ]
    )
    return repository


@pytest.fixture
def service(repo, clock):
    return CatalogService(repo, TTLCache(ttl=60, max_entries=100, clock=clock))


def test_repeated_reads_hit_the_cache(service, repo):
    for _ in range(3):
        assert service.product("MUG-1").price_cents == 900
        assert [p.sku for p in service.category("kitchen")] == ["MUG-1", "MUG-2"]
    assert repo.queries == 2


def test_injected_empty_cache_is_used(repo, clock):
    cache = TTLCache(ttl=60, clock=clock)
    assert len(cache) == 0
    CatalogService(repo, cache).product("MUG-1")
    assert len(cache) == 1


def test_set_price_is_visible_immediately(service):
    service.product("MUG-1")
    assert service.category("kitchen")[0].price_cents == 900
    service.set_price("MUG-1", 950)
    assert service.product("MUG-1").price_cents == 950
    assert service.category("kitchen")[0].price_cents == 950


def test_move_refreshes_both_categories(service):
    assert len(service.category("kitchen")) == 2
    assert len(service.category("lighting")) == 1
    service.move("MUG-2", "lighting")
    assert [p.sku for p in service.category("kitchen")] == ["MUG-1"]
    assert [p.sku for p in service.category("lighting")] == ["LAMP-1", "MUG-2"]


def test_deactivate_and_remove_hide_the_product(service):
    service.product("MUG-1")
    service.category("kitchen")
    service.deactivate("MUG-1")
    with pytest.raises(UnknownProduct):
        service.product("MUG-1")
    assert [p.sku for p in service.category("kitchen")] == ["MUG-2"]
    service.remove("MUG-2")
    with pytest.raises(UnknownProduct):
        service.product("MUG-2")
    assert service.category("kitchen") == []
    with pytest.raises(UnknownProduct):
        service.remove("MUG-2")


def test_add_shows_up_in_a_cached_category(service):
    service.category("kitchen")
    service.add(Product("MUG-3", "Tiny mug", "kitchen", 700))
    assert [p.sku for p in service.category("kitchen")] == ["MUG-1", "MUG-2", "MUG-3"]
    with pytest.raises(ValueError):
        service.add(Product("MUG-3", "Again", "kitchen", 700))


def test_import_refreshes_categories_an_item_left(service):
    service.category("kitchen")
    service.product("MUG-1")
    service.import_products([Product("MUG-1", "Mug", "garden", 800), Product("POT-1", "Pot", "garden", 1500)])
    assert [p.sku for p in service.category("kitchen")] == ["MUG-2"]
    assert [p.sku for p in service.category("garden")] == ["MUG-1", "POT-1"]
    assert service.product("MUG-1").price_cents == 800


def test_writes_start_from_the_stored_row(service, repo):
    service.product("MUG-1")
    repo.save(Product("MUG-1", "Mug (renamed elsewhere)", "kitchen", 900))
    updated = service.set_price("MUG-1", 1000)
    assert updated.name == "Mug (renamed elsewhere)"


def test_external_writes_appear_after_ttl(service, repo, clock):
    assert service.product("LAMP-1").price_cents == 4500
    repo.save(Product("LAMP-1", "Lamp", "lighting", 3900))
    clock.now += 59.9
    assert service.product("LAMP-1").price_cents == 4500
    clock.now += 0.1
    assert service.product("LAMP-1").price_cents == 3900


def test_returned_lists_do_not_alias_the_cache(service):
    service.category("kitchen").clear()
    assert len(service.category("kitchen")) == 2


def test_unknown_sku_is_not_cached(service, repo):
    with pytest.raises(UnknownProduct):
        service.product("NOPE")
    repo.save(Product("NOPE", "Late arrival", "misc", 100))
    assert service.product("NOPE").name == "Late arrival"


def test_least_recently_used_entry_is_evicted(clock):
    cache = TTLCache(ttl=60, max_entries=2, clock=clock)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1
    cache.set("c", 3)
    assert cache.get("b") is MISSING
    assert (cache.get("a"), cache.get("c")) == (1, 3)
    assert cache.stats().evictions == 1


def test_load_overlapping_an_invalidation_is_not_stored(clock):
    cache = TTLCache(ttl=60, clock=clock)

    def loader():
        cache.invalidate("k")
        return "stale"

    assert cache.get_or_load("k", loader) == "stale"
    assert cache.get("k") is MISSING
    assert cache.get_or_load("k", lambda: "fresh") == "fresh"
    assert cache.get("k") == "fresh"


def test_none_values_are_cached(clock):
    cache = TTLCache(ttl=60, clock=clock)
    calls = []
    for _ in range(2):
        assert cache.get_or_load("k", lambda: calls.append(1)) is None
    assert len(calls) == 1


def test_purge_expired_and_invalidate_where(clock):
    cache = TTLCache(ttl=10, clock=clock)
    cache.set(("category", "a"), 1)
    cache.set(("sku", "x"), 2)
    assert cache.invalidate_where(lambda key: key[0] == "category") == 1
    clock.now += 10
    assert cache.purge_expired() == 1
    assert len(cache) == 0


@pytest.mark.parametrize(("ttl", "size"), [(0, 10), (-1, 10), (5, 0)])
def test_bad_configuration_is_rejected(ttl, size):
    with pytest.raises(ValueError):
        TTLCache(ttl=ttl, max_entries=size)
