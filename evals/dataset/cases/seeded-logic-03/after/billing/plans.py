"""Plan catalogue for the subscription product."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    monthly_price_cents: int
    seats: int

    def __post_init__(self) -> None:
        if self.monthly_price_cents < 0:
            raise ValueError(f"{self.code}: price cannot be negative")
        if self.seats < 1:
            raise ValueError(f"{self.code}: a plan includes at least one seat")


CATALOG: dict[str, Plan] = {
    plan.code: plan
    for plan in (
        Plan("starter", "Starter", 1_500, 3),
        Plan("team", "Team", 6_000, 10),
        Plan("business", "Business", 24_000, 50),
    )
}


class UnknownPlan(KeyError):
    pass


def get_plan(code: str) -> Plan:
    try:
        return CATALOG[code]
    except KeyError:
        raise UnknownPlan(code) from None


def upgrades_from(plan: Plan) -> list[Plan]:
    """Plans that cost more than `plan`, cheapest first."""
    pricier = [other for other in CATALOG.values() if other.monthly_price_cents > plan.monthly_price_cents]
    return sorted(pricier, key=lambda other: other.monthly_price_cents)
