"""Catalog operations used by the storefront and the back office."""

from __future__ import annotations

from dataclasses import replace

from catalog.cache import TTLCache
from catalog.repository import Product, ProductRepository

DEFAULT_TTL_SECONDS = 300.0
DEFAULT_MAX_ENTRIES = 10_000


class UnknownProduct(LookupError):
    """No product with that SKU (or, on the storefront, no active one)."""


def _sku_key(sku: str) -> tuple[str, str]:
    return ("sku", sku)


def _category_key(category: str) -> tuple[str, str]:
    return ("category", category)


class CatalogService:
    """Storefront reads are cached.

    Writes made through this service evict the entries they affect immediately; writes made elsewhere
    (another process, a manual fix in the database) become visible once the cached entries expire.
    Back-office writes always start from the stored row, never from the cache.
    """

    def __init__(self, repository: ProductRepository, cache: TTLCache | None = None) -> None:
        self._repository = repository
        self._cache = cache if cache is not None else TTLCache(DEFAULT_TTL_SECONDS, DEFAULT_MAX_ENTRIES)

    def _fetch(self, sku: str) -> Product:
        product = self._repository.get(sku)
        if product is None:
            raise UnknownProduct(sku)
        return product

    def _forget(self, *products: Product) -> None:
        keys: set[tuple[str, str]] = set()
        for product in products:
            keys.add(_sku_key(product.sku))
            keys.add(_category_key(product.category))
        self._cache.invalidate(*keys)

    def product(self, sku: str) -> Product:
        """Storefront lookup: only active products are visible."""
        product = self._cache.get_or_load(_sku_key(sku), lambda: self._fetch(sku))
        if not product.active:
            raise UnknownProduct(sku)
        return product

    def category(self, category: str) -> list[Product]:
        rows = self._cache.get_or_load(
            _category_key(category), lambda: tuple(self._repository.active_in_category(category))
        )
        return list(rows)

    def add(self, product: Product) -> None:
        if product.price_cents <= 0:
            raise ValueError("price must be positive")
        if self._repository.get(product.sku) is not None:
            raise ValueError(f"duplicate sku {product.sku}")
        self._repository.save(product)
        self._forget(product)

    def set_price(self, sku: str, price_cents: int) -> Product:
        if price_cents <= 0:
            raise ValueError("price must be positive")
        updated = replace(self._fetch(sku), price_cents=price_cents)
        self._repository.save(updated)
        self._forget(updated)
        return updated

    def move(self, sku: str, category: str) -> Product:
        current = self._fetch(sku)
        updated = replace(current, category=category)
        self._repository.save(updated)
        self._forget(current, updated)
        return updated

    def deactivate(self, sku: str) -> None:
        updated = replace(self._fetch(sku), active=False)
        self._repository.save(updated)
        self._forget(updated)

    def remove(self, sku: str) -> None:
        current = self._fetch(sku)
        self._repository.delete(sku)
        self._forget(current)

    def import_products(self, products: list[Product]) -> int:
        """Bulk upsert from the supplier feed. Returns how many products were written."""
        if any(product.price_cents <= 0 for product in products):
            raise ValueError("every imported price must be positive")
        self._repository.save_many(products)
        self._cache.invalidate(*(_sku_key(product.sku) for product in products))
        self._cache.invalidate_where(lambda key: key[0] == "category")
        return len(products)
