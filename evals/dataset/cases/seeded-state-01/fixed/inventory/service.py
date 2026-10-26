"""Stock levels per SKU and per-order reservations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from inventory.db import ConnectionPool


class InventoryError(Exception):
    """Base class for errors reported to the caller."""


class UnknownSku(InventoryError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"unknown SKU {sku}")
        self.sku = sku


class InsufficientStock(InventoryError):
    def __init__(self, sku: str, requested: int, free: int) -> None:
        super().__init__(f"{sku}: requested {requested}, only {free} free")
        self.sku = sku
        self.requested = requested
        self.free = free


class DuplicateReservation(InventoryError):
    def __init__(self, order_id: str) -> None:
        super().__init__(f"order {order_id} already holds a reservation")
        self.order_id = order_id


@dataclass(frozen=True)
class StockLevel:
    sku: str
    on_hand: int
    reserved: int

    @property
    def free(self) -> int:
        return self.on_hand - self.reserved


class StockService:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool

    def receive(self, sku: str, quantity: int) -> StockLevel:
        """Add `quantity` units of `sku` to stock, creating the SKU on first delivery."""
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        conn = self._pool.acquire()
        try:
            row = conn.get("stock", sku) or {"on_hand": 0, "reserved": 0}
            row["on_hand"] += quantity
            conn.put("stock", sku, row)
            conn.commit()
        finally:
            self._pool.release(conn)
        return StockLevel(sku, row["on_hand"], row["reserved"])

    def level(self, sku: str) -> StockLevel:
        conn = self._pool.acquire()
        try:
            row = conn.get("stock", sku)
        finally:
            self._pool.release(conn)
        if row is None:
            raise UnknownSku(sku)
        return StockLevel(sku, row["on_hand"], row["reserved"])

    def reserve(self, order_id: str, lines: Sequence[tuple[str, int]]) -> None:
        """Reserve stock for every (sku, quantity) line of an order, all or nothing."""
        if any(quantity <= 0 for _, quantity in lines):
            raise ValueError("quantities must be positive")
        conn = self._pool.acquire()
        try:
            if conn.get("reservations", order_id) is not None:
                raise DuplicateReservation(order_id)
            for sku, quantity in lines:
                row = conn.get("stock", sku)
                if row is None:
                    raise UnknownSku(sku)
                free = row["on_hand"] - row["reserved"]
                if free < quantity:
                    raise InsufficientStock(sku, quantity, free)
                row["reserved"] += quantity
                conn.put("stock", sku, row)
            conn.put("reservations", order_id, {"lines": [[sku, qty] for sku, qty in lines]})
            conn.commit()
        finally:
            self._pool.release(conn)

    def cancel(self, order_id: str) -> bool:
        """Return an order's reserved units to free stock. False if it holds no reservation."""
        conn = self._pool.acquire()
        try:
            reservation = conn.get("reservations", order_id)
            if reservation is None:
                return False
            for sku, quantity in reservation["lines"]:
                row = conn.get("stock", sku)
                row["reserved"] -= quantity
                conn.put("stock", sku, row)
            conn.delete("reservations", order_id)
            conn.commit()
        finally:
            self._pool.release(conn)
        return True
