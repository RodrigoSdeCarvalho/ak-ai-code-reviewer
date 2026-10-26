"""Shipping cost calculation for parcel orders."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

MAX_WEIGHT_KG = Decimal("30")
REMOTE_PREFIXES = frozenset({"HS", "IV", "KW", "PA", "PH", "ZE"})
REMOTE_SURCHARGE = Decimal("6.00")
EXPRESS_MULTIPLIER = Decimal("1.5")


class ParcelTooHeavy(ValueError):
    """The parcel exceeds the heaviest tier the carrier accepts."""


def base_rate(weight_kg: Decimal) -> Decimal:
    """Carrier base price for a parcel. Tiers include their upper bound: exactly 1 kg costs 4.50."""
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    if weight_kg <= Decimal("1"):
        return Decimal("4.50")
    elif weight_kg <= Decimal("5"):
        return Decimal("7.90")
    elif weight_kg <= Decimal("10"):
        return Decimal("11.50")
    elif weight_kg <= Decimal("20"):
        return Decimal("16.00")
    elif weight_kg <= MAX_WEIGHT_KG:
        return Decimal("22.00")
    raise ParcelTooHeavy(f"{weight_kg} kg exceeds the {MAX_WEIGHT_KG} kg limit")


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
