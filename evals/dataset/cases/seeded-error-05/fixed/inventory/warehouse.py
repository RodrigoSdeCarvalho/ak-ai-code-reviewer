"""Stock levels for a single warehouse."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


class UnknownSku(KeyError):
    """The warehouse does not stock this SKU."""


class OutOfStock(Exception):
    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"{sku}: requested {requested}, only {available} available")
        self.sku = sku
        self.requested = requested
        self.available = available


@dataclass
class StockLevel:
    on_hand: int
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


class Warehouse:
    def __init__(self) -> None:
        self._levels: dict[str, StockLevel] = {}

    def receive(self, sku: str, quantity: int) -> None:
        """Add delivered units to stock, creating the SKU on first delivery."""
        _check_quantity(quantity)
        self._levels.setdefault(sku, StockLevel(on_hand=0)).on_hand += quantity

    def level(self, sku: str) -> StockLevel:
        try:
            return self._levels[sku]
        except KeyError:
            raise UnknownSku(sku) from None

    def available(self, sku: str) -> int:
        return self.level(sku).available

    def reserve(self, sku: str, quantity: int) -> None:
        """Hold `quantity` units for an order; raises OutOfStock if fewer are available."""
        _check_quantity(quantity)
        level = self.level(sku)
        if quantity > level.available:
            raise OutOfStock(sku, quantity, level.available)
        level.reserved += quantity

    def reserve_order(self, lines: Iterable[tuple[str, int]]) -> None:
        """Reserve stock for every (sku, quantity) line of one order."""
        done: list[tuple[str, int]] = []
        try:
            for sku, quantity in lines:
                self.reserve(sku, quantity)
                done.append((sku, quantity))
        except Exception:
            for sku, quantity in done:
                self.release(sku, quantity)
            raise

    def release(self, sku: str, quantity: int) -> None:
        """Return reserved units to available stock (order cancelled)."""
        _check_quantity(quantity)
        level = self.level(sku)
        if quantity > level.reserved:
            raise ValueError(f"{sku}: cannot release {quantity}, only {level.reserved} reserved")
        level.reserved -= quantity

    def ship(self, sku: str, quantity: int) -> None:
        """Remove reserved units from stock once they leave the warehouse."""
        _check_quantity(quantity)
        level = self.level(sku)
        if quantity > level.reserved:
            raise ValueError(f"{sku}: cannot ship {quantity}, only {level.reserved} reserved")
        level.reserved -= quantity
        level.on_hand -= quantity


def _check_quantity(quantity: int) -> None:
    if quantity <= 0:
        raise ValueError(f"quantity must be positive, got {quantity}")
