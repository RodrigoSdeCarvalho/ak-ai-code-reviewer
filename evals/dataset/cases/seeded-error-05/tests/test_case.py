from inventory.orders import place_order
from inventory.warehouse import Warehouse


def _warehouse() -> Warehouse:
    warehouse = Warehouse()
    warehouse.receive("MUG-RED", 10)
    warehouse.receive("MUG-BLUE", 3)
    warehouse.receive("TEAPOT", 1)
    return warehouse


def _order(*lines: tuple[str, int]) -> dict:
    return {"lines": [{"sku": sku, "quantity": quantity} for sku, quantity in lines]}


def test_successful_order_reserves_every_line():
    warehouse = _warehouse()
    status, body = place_order(warehouse, _order(("MUG-RED", 4), ("TEAPOT", 1)))
    assert status == 201
    assert body == {"reserved": {"MUG-RED": 4, "TEAPOT": 1}}
    assert warehouse.available("MUG-RED") == 6
    assert warehouse.available("TEAPOT") == 0


def test_rejected_order_leaves_stock_untouched():
    warehouse = _warehouse()
    status, body = place_order(warehouse, _order(("MUG-RED", 4), ("MUG-BLUE", 2), ("TEAPOT", 2)))
    assert (status, body) == (409, {"error": "insufficient stock", "sku": "TEAPOT"})
    assert warehouse.available("MUG-RED") == 10
    assert warehouse.available("MUG-BLUE") == 3
    assert warehouse.level("MUG-RED").reserved == 0


def test_unknown_sku_leaves_stock_untouched():
    warehouse = _warehouse()
    status, _ = place_order(warehouse, _order(("MUG-RED", 4), ("SAUCER", 1)))
    assert status == 404
    assert warehouse.available("MUG-RED") == 10


def test_rejected_orders_do_not_starve_later_orders():
    warehouse = _warehouse()
    for _ in range(3):
        assert place_order(warehouse, _order(("MUG-BLUE", 1), ("TEAPOT", 5)))[0] == 409
    assert place_order(warehouse, _order(("MUG-BLUE", 3)))[0] == 201


def test_invalid_payloads_are_rejected_before_reserving():
    warehouse = _warehouse()
    assert place_order(warehouse, {"lines": []})[0] == 400
    assert place_order(warehouse, _order(("MUG-RED", 1), ("MUG-RED", 2)))[0] == 400
    assert place_order(warehouse, _order(("MUG-RED", 0)))[0] == 400
    assert warehouse.available("MUG-RED") == 10
