from decimal import Decimal

import pytest

from shipping.rates import ParcelTooHeavy, base_rate, rate_table, shipping_cost

EXPECTED = [
    ("0.1", "4.50"),
    ("1", "4.50"),
    ("1.01", "7.90"),
    ("5", "7.90"),
    ("5.5", "11.50"),
    ("10", "11.50"),
    ("10.001", "16.00"),
    ("20", "16.00"),
    ("29.99", "22.00"),
    ("30", "22.00"),
]


@pytest.mark.parametrize(("weight", "price"), EXPECTED)
def test_tier_boundaries_are_upper_inclusive(weight, price):
    assert base_rate(Decimal(weight)) == Decimal(price)


@pytest.mark.parametrize("weight", ["30.01", "45"])
def test_over_the_limit_is_rejected(weight):
    with pytest.raises(ParcelTooHeavy):
        base_rate(Decimal(weight))


@pytest.mark.parametrize("weight", ["0", "-1"])
def test_non_positive_weight_is_rejected(weight):
    with pytest.raises(ValueError):
        base_rate(Decimal(weight))


def test_rate_table_covers_every_tier_contiguously():
    rows = rate_table()
    assert [r["price"] for r in rows] == ["4.50", "7.90", "11.50", "16.00", "22.00"]
    assert rows[0]["over_kg"] == "0"
    assert all(a["up_to_kg"] == b["over_kg"] for a, b in zip(rows, rows[1:]))
    assert rows[-1]["up_to_kg"] == "30"


def test_shipping_cost_with_surcharge_and_express():
    assert shipping_cost(Decimal("2"), "EH1 1AA") == Decimal("7.90")
    assert shipping_cost(Decimal("2"), " iv2 3ab") == Decimal("13.90")
    assert shipping_cost(Decimal("1"), "ZE1 0AA", express=True) == Decimal("15.75")
