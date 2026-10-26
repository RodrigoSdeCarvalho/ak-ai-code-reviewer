"""Keyword search over the in-memory catalogue."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable

from catalog.models import Product

_WORD = re.compile(r"[a-z0-9]+")


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _score(product: Product, words: list[str]) -> int:
    """Two points per query word in the name, one per word in the description; 0 if any word is absent."""
    name = set(_words(product.name))
    description = set(_words(product.description))
    total = 0
    for word in words:
        points = 2 * (word in name) + (word in description)
        if not points:
            return 0
        total += points
    return total


class SearchService:
    def __init__(self, products: Iterable[Product]) -> None:
        self._products = list(products)

    def add(self, product: Product) -> None:
        self._products.append(product)

    def find(self, query: str, tags: Collection[str] = ()) -> list[Product]:
        """Products matching every word of `query` and carrying every tag, best match first."""
        return self._rank(_words(query), frozenset(t.lower() for t in tags))

    def _rank(self, words: list[str], wanted: frozenset[str]) -> list[Product]:
        scored = [
            (score, product)
            for product in self._products
            if wanted <= product.tags and (score := _score(product, words)) > 0
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1].sku))
        return [product for _, product in scored]
