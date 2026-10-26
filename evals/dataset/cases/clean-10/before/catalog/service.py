"""Catalog operations used by the storefront and the back office."""

from __future__ import annotations

from dataclasses import replace

from catalog.repository import Product, ProductRepository


class UnknownProduct(LookupError):
    """No product with that SKU (or, on the storefront, no active one)."""


class CatalogService:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    def _load(self, sku: str) -> Product:
        product = self._repository.get(sku)
        if product is None:
            raise UnknownProduct(sku)
        return product

    def product(self, sku: str) -> Product:
        """Storefront lookup: only active products are visible."""
        product = self._load(sku)
        if not product.active:
            raise UnknownProduct(sku)
        return product

    def category(self, category: str) -> list[Product]:
        return self._repository.active_in_category(category)

    def add(self, product: Product) -> None:
        if product.price_cents <= 0:
            raise ValueError("price must be positive")
        if self._repository.get(product.sku) is not None:
            raise ValueError(f"duplicate sku {product.sku}")
        self._repository.save(product)

    def set_price(self, sku: str, price_cents: int) -> Product:
        if price_cents <= 0:
            raise ValueError("price must be positive")
        updated = replace(self._load(sku), price_cents=price_cents)
        self._repository.save(updated)
        return updated

    def move(self, sku: str, category: str) -> Product:
        updated = replace(self._load(sku), category=category)
        self._repository.save(updated)
        return updated

    def deactivate(self, sku: str) -> None:
        self._repository.save(replace(self._load(sku), active=False))

    def remove(self, sku: str) -> None:
        if not self._repository.delete(sku):
            raise UnknownProduct(sku)

    def import_products(self, products: list[Product]) -> int:
        """Bulk upsert from the supplier feed. Returns how many products were written."""
        if any(product.price_cents <= 0 for product in products):
            raise ValueError("every imported price must be positive")
        self._repository.save_many(products)
        return len(products)
