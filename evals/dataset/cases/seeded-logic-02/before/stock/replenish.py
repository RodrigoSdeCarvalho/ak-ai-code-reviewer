"""Nightly replenishment: decide which SKUs to reorder and how many units to buy."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from stock.models import PurchaseOrder, StockItem


@dataclass(frozen=True)
class ReorderLine:
    sku: str
    quantity: int
    on_hand: int


def needs_reorder(item: StockItem) -> bool:
    return item.on_hand <= item.reorder_point


def round_to_pack(quantity: int, pack_size: int) -> int:
    """Smallest multiple of `pack_size` that is >= `quantity`."""
    packs = -(-quantity // pack_size)
    return packs * pack_size


def order_quantity(item: StockItem) -> int:
    shortfall = item.reorder_up_to - item.on_hand
    if shortfall <= 0:
        return 0
    return round_to_pack(shortfall, item.pack_size)


def plan(items: Iterable[StockItem]) -> list[ReorderLine]:
    """Reorder lines for every item at or below its reorder point, sorted by SKU."""
    lines: list[ReorderLine] = []
    for item in items:
        if not needs_reorder(item):
            continue
        quantity = order_quantity(item)
        if quantity:
            lines.append(ReorderLine(item.sku, quantity, item.on_hand))
    return sorted(lines, key=lambda line: line.sku)


def draft_orders(lines: Iterable[ReorderLine], next_id: int) -> list[PurchaseOrder]:
    """Turn reorder lines into draft purchase orders numbered from `next_id`."""
    orders: list[PurchaseOrder] = []
    for offset, line in enumerate(lines):
        orders.append(PurchaseOrder(f"PO-{next_id + offset:06d}", line.sku, line.quantity))
    return orders
