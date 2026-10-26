from datetime import datetime, timedelta
from decimal import Decimal

from shop.api import list_orders
from shop.orders import Order, OrderRepository
from shop.pagination import paginate


def _repo(n: int, customer_id: int = 7) -> OrderRepository:
    repo = OrderRepository()
    start = datetime(2026, 1, 1, 9, 0)
    for i in range(n):
        repo.add(Order(i + 1, customer_id, Decimal("10.00"), "paid", start + timedelta(hours=i)))
    return repo


def _walk(repo: OrderRepository, per_page: int) -> list[int]:
    seen: list[int] = []
    page = 1
    while True:
        status, body = list_orders(repo, {"customer_id": "7", "page": str(page), "per_page": str(per_page)})
        assert status == 200
        seen += [order["id"] for order in body["orders"]]
        if not body["has_next"]:
            return seen
        page += 1


def test_total_pages_counts_a_partial_last_page():
    assert paginate(list(range(25)), 1, 10).total_pages == 3
    assert paginate(list(range(5)), 1, 20).total_pages == 1
    assert paginate(list(range(20)), 1, 10).total_pages == 2


def test_following_has_next_returns_every_order_once():
    repo = _repo(25)
    assert _walk(repo, 10) == list(range(25, 0, -1))


def test_exact_multiple_of_page_size():
    assert _walk(_repo(20), 10) == list(range(20, 0, -1))


def test_page_contents_and_validation():
    page = paginate(list(range(25)), 3, 10)
    assert page.items == [20, 21, 22, 23, 24]
    assert not page.has_next
    assert paginate([], 1, 10).items == []
    assert list_orders(_repo(3), {"customer_id": "7", "page": "0"})[0] == 400
    assert list_orders(_repo(3), {"customer_id": "7", "per_page": "500"})[0] == 400
