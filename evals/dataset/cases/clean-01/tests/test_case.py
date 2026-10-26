from datetime import date

import pytest

from reports.dashboard import panel_from_query
from reports.db import NewOrder, connect, insert_orders
from reports.orders_report import orders_between


@pytest.fixture
def conn():
    conn = connect()
    insert_orders(
        conn,
        [
            NewOrder("carol", "paid", 4200, date(2026, 3, 1)),
            NewOrder("alice", "shipped", 1500, date(2026, 3, 2)),
            NewOrder("bob", "refunded", 9900, date(2026, 3, 2)),
            NewOrder("alice", "pending", 1500, date(2026, 3, 5)),
            NewOrder("dave", "paid", 700, date(2026, 4, 1)),
        ],
    )
    return conn


def ids(rows):
    return [r.order_id for r in rows]


def test_default_order_is_newest_first_with_id_tiebreak(conn):
    rows = orders_between(conn, date(2026, 3, 1), date(2026, 3, 31))
    assert ids(rows) == [4, 3, 2, 1]


def test_sort_by_total_both_directions(conn):
    start, end = date(2026, 3, 1), date(2026, 3, 31)
    assert ids(orders_between(conn, start, end, sort="total", descending=False)) == [2, 4, 1, 3]
    assert ids(orders_between(conn, start, end, sort="total")) == [3, 1, 4, 2]


def test_status_filter_uses_bound_values(conn):
    rows = orders_between(conn, date(2026, 3, 1), date(2026, 4, 30), statuses=["paid", "shipped"])
    assert ids(rows) == [5, 2, 1]
    assert orders_between(conn, date(2026, 3, 1), date(2026, 4, 30), statuses=[]) == []


@pytest.mark.parametrize("sort", ["id", "total; DROP TABLE orders", "placed_on DESC --"])
def test_unknown_sort_key_is_rejected_and_table_survives(conn, sort):
    with pytest.raises(ValueError):
        orders_between(conn, date(2026, 3, 1), date(2026, 3, 31), sort=sort)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 5


def test_unknown_status_is_rejected(conn):
    with pytest.raises(ValueError):
        orders_between(conn, date(2026, 3, 1), date(2026, 3, 31), statuses=["paid' OR '1'='1"])


def test_panel_from_query(conn):
    panel = panel_from_query(conn, {"start": "2026-03-01", "end": "2026-03-31", "status": "paid, shipped", "sort": "customer"})
    assert [o["customer"] for o in panel["orders"]] == ["alice", "carol"]
    assert panel["revenue"] == "57.00"
    default = panel_from_query(conn, {"start": "2026-03-01", "end": "2026-03-31", "status": ""})
    assert [o["id"] for o in default["orders"]] == [4, 3, 2, 1]
    assert default["top_customers"][0] == {"customer": "carol", "spend": "42.00"}


def test_panel_from_query_requires_dates(conn):
    with pytest.raises(ValueError, match="end"):
        panel_from_query(conn, {"start": "2026-03-01"})
