"""Nightly replenishment: decide which SKUs to reorder and how many units to buy.

Decisions use the inventory position (stock on hand, minus units reserved for open sales orders, plus
units already on order), so a SKU that is short today but has a delivery coming is not ordered twice.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from stock.models import POStatus, PurchaseOrder, StockItem


@dataclass(frozen=True)
class Position:
    on_hand: int
    reserved: int
    inbound: int

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved + self.inbound


@dataclass(frozen=True)
class ReorderLine:
    sku: str
    quantity: int
    position: Position


def inbound_by_sku(purchase_orders: Iterable[PurchaseOrder]) -> Counter[str]:
    """Units per SKU that have been ordered from suppliers but are not in stock yet."""
    inbound: Counter[str] = Counter()
    for order in purchase_orders:
        if order.status in (POStatus.DRAFT, POStatus.SUBMITTED):
            inbound[order.sku] += order.quantity
    return inbound


def position_of(item: StockItem, inbound: Mapping[str, int]) -> Position:
    return Position(item.on_hand, item.reserved, inbound.get(item.sku, 0))


def needs_reorder(item: StockItem, position: Position) -> bool:
    return position.available <= item.reorder_point


def round_to_pack(quantity: int, pack_size: int) -> int:
    """Smallest multiple of `pack_size` that is >= `quantity`."""
    packs = -(-quantity // pack_size)
    return packs * pack_size


def order_quantity(item: StockItem, position: Position) -> int:
    shortfall = item.reorder_up_to - position.available
    if shortfall <= 0:
        return 0
    return round_to_pack(shortfall, item.pack_size)


def plan(items: Iterable[StockItem], purchase_orders: Iterable[PurchaseOrder] = ()) -> list[ReorderLine]:
    """Reorder lines for every item whose position is at or below its reorder point, sorted by SKU."""
    inbound = inbound_by_sku(purchase_orders)
    lines: list[ReorderLine] = []
    for item in items:
        position = position_of(item, inbound)
        if not needs_reorder(item, position):
            continue
        quantity = order_quantity(item, position)
        if quantity:
            lines.append(ReorderLine(item.sku, quantity, position))
    return sorted(lines, key=lambda line: line.sku)


def draft_orders(lines: Iterable[ReorderLine], next_id: int) -> list[PurchaseOrder]:
    """Turn reorder lines into draft purchase orders numbered from `next_id`."""
    orders: list[PurchaseOrder] = []
    for offset, line in enumerate(lines):
        orders.append(PurchaseOrder(f"PO-{next_id + offset:06d}", line.sku, line.quantity))
    return orders
