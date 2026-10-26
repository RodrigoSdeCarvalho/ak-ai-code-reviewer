"""Daily sales totals for the store managers' report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from salesreport.records import Sale


@dataclass(frozen=True)
class DayTotal:
    day: date
    amount_cents: int
    transactions: int

    @property
    def average_cents(self) -> int:
        if not self.transactions:
            return 0
        return round(self.amount_cents / self.transactions)


def daily_totals(sales: Iterable[Sale], since: date, until: date, store: str | None = None) -> list[DayTotal]:
    """One row per calendar day from `since` to `until` inclusive, oldest first.

    Days without sales get a zero row so gaps are visible; sales outside the range are ignored.
    """
    if until < since:
        raise ValueError(f"until ({until}) is before since ({since})")
    amounts: defaultdict[date, int] = defaultdict(int)
    counts: defaultdict[date, int] = defaultdict(int)
    for sale in sales:
        if store is not None and sale.store != store:
            continue
        if not since <= sale.day <= until:
            continue
        amounts[sale.day] += sale.amount_cents
        counts[sale.day] += 1
    days = (until - since).days + 1
    return [DayTotal(day, amounts[day], counts[day]) for day in (since + timedelta(n) for n in range(days))]


def format_report(rows: list[DayTotal]) -> str:
    header = f"{'day':<12}{'sales':>14}{'count':>8}{'avg':>12}"
    body = [
        f"{row.day.isoformat():<12}{row.amount_cents / 100:>14,.2f}{row.transactions:>8}{row.average_cents / 100:>12,.2f}"
        for row in rows
    ]
    total = sum(row.amount_cents for row in rows)
    count = sum(row.transactions for row in rows)
    footer = f"{'total':<12}{total / 100:>14,.2f}{count:>8}"
    return "\n".join([header, *body, footer])
