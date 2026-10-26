"""Invoices issued at the start of each billing period."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from billing.subscriptions import Subscription

DEFAULT_TAX_RATE = Decimal("0.20")


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole:,}.{frac:02d}"


class LineKind(str, Enum):
    RECURRING = "recurring"
    PRORATION = "proration"


@dataclass(frozen=True)
class LineItem:
    description: str
    amount_cents: int
    kind: LineKind = LineKind.RECURRING


@dataclass(frozen=True)
class Invoice:
    customer_id: str
    period_start: date
    period_end: date
    lines: tuple[LineItem, ...]
    tax_rate: Decimal

    @property
    def subtotal_cents(self) -> int:
        return sum(line.amount_cents for line in self.lines)

    @property
    def tax_cents(self) -> int:
        tax = Decimal(self.subtotal_cents) * self.tax_rate
        return int(tax.quantize(Decimal(1), rounding=ROUND_HALF_UP))

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.tax_cents

    def lines_of(self, kind: LineKind) -> list[LineItem]:
        return [line for line in self.lines if line.kind is kind]

    def render(self) -> str:
        rows = [f"Invoice for {self.customer_id}, {self.period_start} to {self.period_end}"]
        for line in self.lines:
            rows.append(f"  {line.description:<48} {format_cents(line.amount_cents):>12}")
        rows.append(f"  {'Subtotal':<48} {format_cents(self.subtotal_cents):>12}")
        rows.append(f"  {'Tax':<48} {format_cents(self.tax_cents):>12}")
        rows.append(f"  {'Total':<48} {format_cents(self.total_cents):>12}")
        return "\n".join(rows)


def build_invoice(sub: Subscription, tax_rate: Decimal = DEFAULT_TAX_RATE) -> Invoice:
    """Invoice for the subscription's current period, including adjustments queued since the last one."""
    from billing.subscriptions import Status

    if sub.status is not Status.ACTIVE:
        raise ValueError(f"{sub.customer_id}: no invoice for a cancelled subscription")
    recurring = LineItem(f"{sub.plan.name} plan", sub.plan.monthly_price_cents)
    lines = (*sub.take_pending_lines(), recurring)
    return Invoice(sub.customer_id, sub.period_start, sub.period_end, lines, tax_rate)
