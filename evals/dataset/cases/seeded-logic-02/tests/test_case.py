from datetime import date

from stock.models import POStatus, PurchaseOrder, StockItem, receive
from stock.nightly import OrderBook, run
from stock.replenish import inbound_by_sku, plan


def _item(on_hand: int, reserved: int = 0) -> StockItem:
    return StockItem("SKU-1", on_hand, reorder_point=20, reorder_up_to=100, pack_size=10, reserved=reserved)


def test_received_orders_are_not_counted_again_as_inbound():
    item = _item(10)
    po = PurchaseOrder("PO-000001", "SKU-1", 50)
    po.submit(date(2026, 3, 2))
    receive(po, item)
    item.on_hand -= 45
    assert item.on_hand == 15
    lines = plan([item], [po])
    assert [(line.sku, line.quantity) for line in lines] == [("SKU-1", 90)]
    assert lines[0].position.available == 15


def test_nightly_run_reorders_after_a_delivery_has_been_sold_through():
    item = _item(10)
    book = OrderBook()
    first = run({"SKU-1": item}, book)
    assert [order.quantity for order in first.created] == [90]
    book.orders[0].submit(date(2026, 3, 2))
    receive(book.orders[0], item)
    item.on_hand = 5
    second = run({"SKU-1": item}, book)
    assert [order.quantity for order in second.created] == [100]
    assert inbound_by_sku(book.orders)["SKU-1"] == 100


def test_open_orders_count_and_cancelled_ones_do_not():
    submitted = PurchaseOrder("PO-1", "SKU-1", 40, POStatus.SUBMITTED)
    cancelled = PurchaseOrder("PO-2", "SKU-1", 70, POStatus.CANCELLED)
    draft = PurchaseOrder("PO-3", "SKU-2", 5)
    assert inbound_by_sku([submitted, cancelled, draft]) == {"SKU-1": 40, "SKU-2": 5}
    small = PurchaseOrder("PO-5", "SKU-1", 5, POStatus.SUBMITTED)
    assert [(line.quantity, line.position.inbound) for line in plan([_item(10)], [small])] == [(90, 5)]
    assert plan([_item(10)], [PurchaseOrder("PO-4", "SKU-1", 30, POStatus.SUBMITTED)]) == []


def test_reservations_reduce_the_position():
    assert plan([_item(30)]) == []
    assert [line.quantity for line in plan([_item(30, reserved=15)])] == [90]


def test_second_run_does_not_duplicate_drafts():
    item = _item(10)
    book = OrderBook()
    run({"SKU-1": item}, book)
    again = run({"SKU-1": item}, book)
    assert again.created == []
    assert again.describe() == "nothing to reorder"
