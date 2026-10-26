from catalog.handlers import search_products
from catalog.models import make_product
from catalog.service import SearchService


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _service(clock: FakeClock) -> SearchService:
    return SearchService(
        [
            make_product("K1", "Steel chef knife", "89.00", 4.8, "forged steel blade", "kitchen"),
            make_product("K2", "Paring knife", "15.00", 4.1, "small steel blade for fruit", "kitchen"),
            make_product("K3", "Bread knife", "32.00", 3.9, "serrated knife", "kitchen"),
            make_product("G1", "Garden knife", "21.00", 4.5, "folding blade", "garden"),
        ],
        clock=clock,
    )


def _skus(body: dict) -> list[str]:
    return [item["sku"] for item in body["results"]]


def test_relevance_order_survives_an_earlier_sorted_request():
    service = _service(FakeClock())
    status, first = search_products(service, {"q": "knife"})
    assert status == 200
    relevance = _skus(first)
    _, by_price = search_products(service, {"q": "knife", "sort": "price"})
    assert _skus(by_price) == ["K2", "G1", "K3", "K1"]
    _, again = search_products(service, {"q": "knife"})
    assert _skus(again) == relevance


def test_sorted_first_request_does_not_change_later_relevance_results():
    service = _service(FakeClock())
    search_products(service, {"q": "blade", "sort": "-price"})
    _, body = search_products(service, {"q": "blade"})
    assert _skus(body) == ["G1", "K1", "K2"]


def test_cache_expires_and_is_cleared_on_add():
    clock = FakeClock()
    service = _service(clock)
    assert [p.sku for p in service.find("knife", ["garden"])] == ["G1"]
    service.add(make_product("G2", "Pruning knife", "18.00", 4.0, "", "garden"))
    assert [p.sku for p in service.find("knife", ["garden"])] == ["G1", "G2"]
    clock.now += 61
    assert [p.sku for p in service.find("knife", ["Garden"])] == ["G1", "G2"]


def test_validation_and_limit():
    service = _service(FakeClock())
    assert search_products(service, {"q": " "})[0] == 400
    assert search_products(service, {"q": "knife", "sort": "name"})[0] == 400
    assert search_products(service, {"q": "knife", "limit": "0"})[0] == 400
    status, body = search_products(service, {"q": "knife", "sort": "rating", "limit": "2"})
    assert status == 200
    assert body["count"] == 4
    assert _skus(body) == ["K1", "G1"]
