"""Keyword search over the in-memory catalogue."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Collection, Iterable

from catalog.models import Product

_WORD = re.compile(r"[a-z0-9]+")

CacheKey = tuple[tuple[str, ...], frozenset[str]]


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
    def __init__(
        self,
        products: Iterable[Product],
        ttl: float = 60.0,
        max_entries: int = 512,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._products = list(products)
        self._ttl = ttl
        self._max_entries = max_entries
        self._clock = clock
        self._cache: dict[CacheKey, tuple[float, list[Product]]] = {}

    def add(self, product: Product) -> None:
        self._products.append(product)
        self._cache.clear()

    def find(self, query: str, tags: Collection[str] = ()) -> list[Product]:
        """Products matching every word of `query` and carrying every tag, best match first.

        Results are cached per query and tag set for `ttl` seconds, or until a product is added.
        """
        words = _words(query)
        wanted = frozenset(t.lower() for t in tags)
        key = (tuple(words), wanted)
        now = self._clock()
        entry = self._cache.pop(key, None)
        if entry is not None and now - entry[0] < self._ttl:
            self._cache[key] = entry
            return entry[1]
        hits = self._rank(words, wanted)
        if len(self._cache) >= self._max_entries:
            del self._cache[next(iter(self._cache))]
        self._cache[key] = (now, hits)
        return hits

    def _rank(self, words: list[str], wanted: frozenset[str]) -> list[Product]:
        scored = [
            (score, product)
            for product in self._products
            if wanted <= product.tags and (score := _score(product, words)) > 0
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1].sku))
        return [product for _, product in scored]
