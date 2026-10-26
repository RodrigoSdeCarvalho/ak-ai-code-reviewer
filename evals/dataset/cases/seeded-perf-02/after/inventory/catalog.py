"""Catalog items and the on-hand quantities the system believes are in stock."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogItem:
    sku: str
    description: str
    on_hand: int
    active: bool = True


class Catalog:
    def __init__(self, items: Iterable[CatalogItem] = ()) -> None:
        self._items: dict[str, CatalogItem] = {}
        for item in items:
            self.add(item)

    def add(self, item: CatalogItem) -> None:
        if item.sku in self._items:
            raise ValueError(f"duplicate sku {item.sku}")
        if item.on_hand < 0:
            raise ValueError(f"negative on-hand quantity for {item.sku}")
        self._items[item.sku] = item

    def get(self, sku: str) -> CatalogItem | None:
        return self._items.get(sku)

    def __iter__(self) -> Iterator[CatalogItem]:
        return iter(self._items.values())

    def __len__(self) -> int:
        return len(self._items)

    def active(self) -> list[CatalogItem]:
        return [item for item in self._items.values() if item.active]
