"""Product storage. The in-memory implementation stands in for the database in tests and local runs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price_cents: int
    active: bool = True


class ProductRepository:
    """Products keyed by SKU. `queries` counts reads, the way the database driver's metrics do."""

    def __init__(self) -> None:
        self._rows: dict[str, Product] = {}
        self.queries = 0

    def get(self, sku: str) -> Product | None:
        self.queries += 1
        return self._rows.get(sku)

    def active_in_category(self, category: str) -> list[Product]:
        """Active products of one category, ordered by SKU."""
        self.queries += 1
        rows = (product for product in self._rows.values() if product.category == category and product.active)
        return sorted(rows, key=lambda product: product.sku)

    def save(self, product: Product) -> None:
        self._rows[product.sku] = product

    def save_many(self, products: list[Product]) -> None:
        for product in products:
            self._rows[product.sku] = product

    def delete(self, sku: str) -> bool:
        return self._rows.pop(sku, None) is not None
