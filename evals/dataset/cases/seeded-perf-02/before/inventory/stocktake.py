"""Reconcile a physical stocktake against the catalog's on-hand quantities."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from inventory.catalog import Catalog


@dataclass(frozen=True)
class Scan:
    sku: str
    location: str
    quantity: int


@dataclass(frozen=True)
class Variance:
    sku: str
    expected: int
    counted: int

    @property
    def delta(self) -> int:
        return self.counted - self.expected


@dataclass
class Reconciliation:
    variances: list[Variance] = field(default_factory=list)
    matched: int = 0

    @property
    def net_delta(self) -> int:
        return sum(v.delta for v in self.variances)


def count_by_sku(scans: Iterable[Scan]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for scan in scans:
        if scan.quantity < 0:
            raise ValueError(f"negative count for {scan.sku} at {scan.location}")
        totals[scan.sku] += scan.quantity
    return dict(totals)


def reconcile(catalog: Catalog, scans: Iterable[Scan]) -> Reconciliation:
    counted = count_by_sku(scans)
    result = Reconciliation()
    for item in catalog.active():
        quantity = counted.get(item.sku, 0)
        if quantity == item.on_hand:
            result.matched += 1
        else:
            result.variances.append(Variance(item.sku, item.on_hand, quantity))
    result.variances.sort(key=lambda v: (-abs(v.delta), v.sku))
    return result
