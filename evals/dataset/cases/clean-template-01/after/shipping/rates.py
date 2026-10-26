"""Shipping cost calculation for parcel orders."""

from __future__ import annotations

from bisect import bisect_left
from decimal import ROUND_HALF_UP, Decimal

# (upper weight bound in kg, base price), ascending. A tier includes its upper bound: exactly 1 kg costs 4.50.
RATE_TIERS: tuple[tuple[Decimal, Decimal], ...] = (
    (Decimal("1"), Decimal("4.50")),
    (Decimal("5"), Decimal("7.90")),
    (Decimal("10"), Decimal("11.50")),
    (Decimal("20"), Decimal("16.00")),
    (Decimal("30"), Decimal("22.00")),
)
_UPPER_BOUNDS = [bound for bound, _ in RATE_TIERS]
MAX_WEIGHT_KG = _UPPER_BOUNDS[-1]
REMOTE_PREFIXES = frozenset({"HS", "IV", "KW", "PA", "PH", "ZE"})
REMOTE_SURCHARGE = Decimal("6.00")
EXPRESS_MULTIPLIER = Decimal("1.5")


class ParcelTooHeavy(ValueError):
    """The parcel exceeds the heaviest tier the carrier accepts."""


def base_rate(weight_kg: Decimal) -> Decimal:
    """Carrier base price for a parcel, looked up in RATE_TIERS."""
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    index = bisect_left(_UPPER_BOUNDS, weight_kg)
    if index == len(_UPPER_BOUNDS):
        raise ParcelTooHeavy(f"{weight_kg} kg exceeds the {MAX_WEIGHT_KG} kg limit")
    return RATE_TIERS[index][1]


def rate_table() -> list[dict[str, str]]:
    """The tier table for the public pricing page: one row per tier with its weight range and price."""
    rows: list[dict[str, str]] = []
    lower = Decimal("0")
    for upper, price in RATE_TIERS:
        rows.append({"over_kg": str(lower), "up_to_kg": str(upper), "price": str(price)})
        lower = upper
    return rows


def remote_surcharge(postcode: str) -> Decimal:
    """Flat surcharge for Highlands and Islands postcodes."""
    area = postcode.strip().upper()[:2]
    return REMOTE_SURCHARGE if area in REMOTE_PREFIXES else Decimal("0")


def shipping_cost(weight_kg: Decimal, postcode: str, express: bool = False) -> Decimal:
    """Total shipping price, rounded to the penny."""
    cost = base_rate(weight_kg) + remote_surcharge(postcode)
    if express:
        cost *= EXPRESS_MULTIPLIER
    return cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
