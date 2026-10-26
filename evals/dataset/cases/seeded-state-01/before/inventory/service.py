"""Stock levels per SKU."""

from __future__ import annotations

from dataclasses import dataclass

from inventory.db import ConnectionPool


class InventoryError(Exception):
    """Base class for errors reported to the caller."""


class UnknownSku(InventoryError):
    def __init__(self, sku: str) -> None:
        super().__init__(f"unknown SKU {sku}")
        self.sku = sku


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
