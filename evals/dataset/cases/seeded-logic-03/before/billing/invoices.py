"""Invoices issued at the start of each billing period."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from billing.subscriptions import Status, Subscription

DEFAULT_TAX_RATE = Decimal("0.20")


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{frac:02d}"


@dataclass(frozen=True)
class Invoice:
    customer_id: str
    period_start: date
    period_end: date
    description: str
    amount_cents: int
    tax_rate: Decimal

    @property
    def tax_cents(self) -> int:
        tax = Decimal(self.amount_cents) * self.tax_rate
        return int(tax.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    @property
    def total_cents(self) -> int:
        return self.amount_cents + self.tax_cents

    def render(self) -> str:
        return "\n".join(
            [
                f"Invoice for {self.customer_id}, {self.period_start} to {self.period_end}",
                f"  {self.description:<40} {format_cents(self.amount_cents):>12}",
                f"  {'Tax':<40} {format_cents(self.tax_cents):>12}",
                f"  {'Total':<40} {format_cents(self.total_cents):>12}",
            ]
        )


def build_invoice(sub: Subscription, tax_rate: Decimal = DEFAULT_TAX_RATE) -> Invoice:
    """Invoice for the subscription's current period."""
    if sub.status is not Status.ACTIVE:
        raise ValueError(f"{sub.customer_id}: no invoice for a cancelled subscription")
    return Invoice(
        sub.customer_id,
        sub.period_start,
        sub.period_end,
        f"{sub.plan.name} plan",
        sub.plan.monthly_price_cents,
        tax_rate,
    )
