"""Warehouse stock records and purchase orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class POStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RECEIVED = "received"
    CANCELLED = "cancelled"


@dataclass
class StockItem:
    sku: str
    on_hand: int
    reorder_point: int
    reorder_up_to: int
    pack_size: int = 1
    reserved: int = 0

    def __post_init__(self) -> None:
        if self.pack_size < 1:
            raise ValueError(f"{self.sku}: pack_size must be >= 1")
        if self.reorder_up_to < self.reorder_point:
            raise ValueError(f"{self.sku}: reorder_up_to must be >= reorder_point")


@dataclass
class PurchaseOrder:
    po_id: str
    sku: str
    quantity: int
    status: POStatus = POStatus.DRAFT
    expected_on: date | None = None
    notes: list[str] = field(default_factory=list)

    def submit(self, expected_on: date) -> None:
        if self.status is not POStatus.DRAFT:
            raise ValueError(f"{self.po_id}: only draft orders can be submitted")
        self.status = POStatus.SUBMITTED
        self.expected_on = expected_on

    def cancel(self, reason: str) -> None:
        if self.status is POStatus.RECEIVED:
            raise ValueError(f"{self.po_id}: received orders cannot be cancelled")
        self.status = POStatus.CANCELLED
        self.notes.append(reason)


def receive(order: PurchaseOrder, item: StockItem) -> None:
    """Book a delivered order into stock: the quantity moves into `on_hand`."""
    if order.sku != item.sku:
        raise ValueError(f"{order.po_id} is for {order.sku}, not {item.sku}")
    if order.status is not POStatus.SUBMITTED:
        raise ValueError(f"{order.po_id}: only submitted orders can be received")
    item.on_hand += order.quantity
    order.status = POStatus.RECEIVED
