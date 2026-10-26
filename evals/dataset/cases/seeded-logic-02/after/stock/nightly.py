"""Nightly replenishment job: plan reorders and record them as draft purchase orders."""

from __future__ import annotations

from dataclasses import dataclass, field

from stock.models import PurchaseOrder, StockItem
from stock.replenish import ReorderLine, draft_orders, plan


@dataclass
class OrderBook:
    """Every purchase order the warehouse has raised, in creation order."""

    orders: list[PurchaseOrder] = field(default_factory=list)

    def next_id(self) -> int:
        return len(self.orders) + 1

    def add(self, orders: list[PurchaseOrder]) -> None:
        self.orders.extend(orders)

    def for_sku(self, sku: str) -> list[PurchaseOrder]:
        return [order for order in self.orders if order.sku == sku]


@dataclass(frozen=True)
class RunSummary:
    lines: list[ReorderLine]
    created: list[PurchaseOrder]

    def describe(self) -> str:
        if not self.lines:
            return "nothing to reorder"
        parts = [f"{line.sku} x{line.quantity} (available {line.position.available})" for line in self.lines]
        return f"{len(self.created)} draft orders: " + ", ".join(parts)


def run(stock: dict[str, StockItem], book: OrderBook) -> RunSummary:
    lines = plan(stock.values(), book.orders)
    created = draft_orders(lines, book.next_id())
    book.add(created)
    return RunSummary(lines, created)
