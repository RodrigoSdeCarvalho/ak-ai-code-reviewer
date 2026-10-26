"""Roll usage events up into daily and monthly totals per account and metric."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date

from metering.events import UsageEvent

UsageKey = tuple[str, str, str]
"""(account_id, metric, month) with month formatted as YYYY-MM."""


@dataclass(frozen=True)
class DailyTotal:
    account_id: str
    metric: str
    day: date
    quantity: int


@dataclass
class MonthlyUsage:
    account_id: str
    metric: str
    month: str
    total: int
    active_days: int
    peak_day: date
    peak_quantity: int

    @property
    def average_per_active_day(self) -> float:
        return self.total / self.active_days


def month_key(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def previous_month(month: str) -> str:
    """The YYYY-MM month before `month`."""
    year, number = (int(part) for part in month.split("-"))
    if number == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{number - 1:02d}"


def daily_totals(events: Iterable[UsageEvent]) -> Iterator[DailyTotal]:
    """Quantity per account, metric and UTC day, in account/metric/day order."""
    ordered = sorted(events, key=lambda event: (event.account_id, event.metric, event.timestamp))
    current: tuple[str, str, date] | None = None
    quantity = 0
    for event in ordered:
        key = (event.account_id, event.metric, event.timestamp.date())
        if current is not None and key != current:
            yield DailyTotal(*current, quantity)
            quantity = 0
        current = key
        quantity += event.quantity
    if current is not None:
        yield DailyTotal(*current, quantity)


def monthly_usage(daily: Iterable[DailyTotal]) -> dict[UsageKey, MonthlyUsage]:
    """Monthly totals, active days and the peak day for each account and metric."""
    usage: dict[UsageKey, MonthlyUsage] = {}
    for total in daily:
        month = month_key(total.day)
        key = (total.account_id, total.metric, month)
        current = usage.get(key)
        if current is None:
            usage[key] = MonthlyUsage(
                account_id=total.account_id,
                metric=total.metric,
                month=month,
                total=total.quantity,
                active_days=1,
                peak_day=total.day,
                peak_quantity=total.quantity,
            )
            continue
        current.total += total.quantity
        current.active_days += 1
        if total.quantity > current.peak_quantity:
            current.peak_day = total.day
            current.peak_quantity = total.quantity
    return usage


def rollup(events: Iterable[UsageEvent]) -> dict[UsageKey, MonthlyUsage]:
    return monthly_usage(daily_totals(events))
