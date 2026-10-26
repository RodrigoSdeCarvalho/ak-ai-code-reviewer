"""Mid-period plan changes: credit the unused part of the old plan, charge the rest on the new one."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from billing.invoices import LineItem, LineKind, format_cents
from billing.plans import Plan

if TYPE_CHECKING:
    from billing.subscriptions import Subscription


def prorate(amount_cents: int, days: int, period_days: int) -> int:
    """`amount_cents` scaled by days / period_days, rounded half up to a whole cent."""
    if period_days <= 0:
        raise ValueError("a billing period is at least one day long")
    if not 0 <= days <= period_days:
        raise ValueError(f"days must be between 0 and {period_days}, got {days}")
    scaled = Decimal(amount_cents) * days / period_days
    return int(scaled.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def split_period(start: date, end: date, on: date) -> tuple[int, int]:
    """(used, remaining) days of the period [start, end) for a change that takes effect on `on`."""
    if not start <= on < end:
        raise ValueError(f"{on} is outside the billing period {start} to {end}")
    used = (on - start).days
    return used, (end - start).days - used


def plan_change_lines(sub: Subscription, new_plan: Plan, on: date) -> list[LineItem]:
    """Credit and charge lines for moving `sub` from its current plan to `new_plan` on `on`."""
    period_days = (sub.period_end - sub.period_start).days
    used, remaining = split_period(sub.period_start, sub.period_end, on)
    old_plan = sub.plan
    credit = prorate(old_plan.monthly_price_cents, used, period_days)
    charge = prorate(new_plan.monthly_price_cents, remaining, period_days)
    last_day = sub.period_end - timedelta(days=1)
    span = f"{on.isoformat()} to {last_day.isoformat()}"
    return [
        LineItem(f"Unused {old_plan.name} ({span})", -credit, LineKind.PRORATION),
        LineItem(f"{new_plan.name} ({span})", charge, LineKind.PRORATION),
    ]


def preview_change(sub: Subscription, new_plan: Plan, on: date) -> str:
    """One-line summary of what a plan change would add to the next invoice, before tax."""
    lines = plan_change_lines(sub, new_plan, on)
    net = sum(line.amount_cents for line in lines)
    verb = "charge" if net >= 0 else "credit"
    return f"Switching to {new_plan.name} on {on.isoformat()}: {verb} of {format_cents(abs(net))} before tax"
