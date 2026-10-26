import pytest
from inventory.catalog import Catalog, CatalogItem
from inventory.stocktake import Scan, reconcile


class CountingSku(str):
    comparisons = 0

    def __eq__(self, other: object) -> bool:
        CountingSku.comparisons += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


def _sku(n: int) -> CountingSku:
    return CountingSku(f"SKU-{n:05d}")


def _catalog(n: int) -> Catalog:
    return Catalog(CatalogItem(_sku(i), f"item {i}", on_hand=4, active=i % 10 != 0) for i in range(n))


def test_sku_comparisons_stay_linear_in_scan_count():
    catalog = _catalog(600)
    scans = [Scan(_sku(i), f"A{i % 7}", 4) for i in range(600)]
    CountingSku.comparisons = 0
    reconcile(catalog, scans)
    assert CountingSku.comparisons <= 4 * len(scans)


def test_unknown_and_inactive_skus_are_reported_with_locations():
    catalog = Catalog(
        [
            CatalogItem("BOLT-M6", "bolt", 10),
            CatalogItem("NUT-M6", "nut", 5),
            CatalogItem("OLD-1", "retired", 2, active=False),
        ]
    )
    scans = [
        Scan("BOLT-M6", "A1", 6),
        Scan("BOLT-M6", "B2", 4),
        Scan("NUT-M6", "A1", 3),
        Scan("OLD-1", "C3", 2),
        Scan("MYSTERY", "C3", 1),
        Scan("MYSTERY", "D4", 1),
    ]
    result = reconcile(catalog, scans)
    assert result.unknown == {"OLD-1": ["C3"], "MYSTERY": ["C3", "D4"]}
    assert result.matched == 1
    assert [(v.sku, v.delta) for v in result.variances] == [("NUT-M6", -2)]
    assert result.net_delta == -2


def test_unscanned_active_items_count_as_zero():
    result = reconcile(Catalog([CatalogItem("A", "a", 3), CatalogItem("B", "b", 0)]), iter([]))
    assert result.matched == 1
    assert [(v.sku, v.counted) for v in result.variances] == [("A", 0)]
    assert result.unknown == {}


def test_negative_counts_are_rejected_for_unknown_skus_too():
    with pytest.raises(ValueError):
        reconcile(Catalog([CatalogItem("A", "a", 3)]), [Scan("A", "A1", 3), Scan("GHOST", "B2", -1)])
