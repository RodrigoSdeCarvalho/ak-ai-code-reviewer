"""Catalogue data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price: Decimal
    rating: float
    description: str = ""
    tags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError(f"{self.sku}: price must not be negative")
        if not 0 <= self.rating <= 5:
            raise ValueError(f"{self.sku}: rating must be between 0 and 5")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sku": self.sku,
            "name": self.name,
            "price": str(self.price),
            "rating": self.rating,
            "tags": sorted(self.tags),
        }


def make_product(sku: str, name: str, price: str, rating: float, description: str = "", tags: str = "") -> Product:
    """Build a product from loosely typed input such as a CSV row."""
    return Product(
        sku=sku,
        name=name,
        price=Decimal(price),
        rating=rating,
        description=description,
        tags=frozenset(t.strip().lower() for t in tags.split(",") if t.strip()),
    )
