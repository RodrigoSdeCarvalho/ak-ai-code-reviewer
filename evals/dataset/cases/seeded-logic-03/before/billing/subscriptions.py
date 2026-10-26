"""Customer subscriptions billed monthly in advance."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from enum import Enum

from billing.plans import Plan


class Status(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


def add_month(day: date, anchor_day: int) -> date:
    """The date one month after `day`, on `anchor_day` or the last day of a shorter month."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last))


@dataclass
class Subscription:
    """A subscription whose current billing period is [period_start, period_end)."""

    customer_id: str
    plan: Plan
    period_start: date
    period_end: date
    anchor_day: int
    status: Status = Status.ACTIVE

    @classmethod
    def start(cls, customer_id: str, plan: Plan, on: date) -> Subscription:
        return cls(customer_id, plan, on, add_month(on, on.day), on.day)

    def renew(self) -> None:
        if self.status is not Status.ACTIVE:
            raise ValueError(f"{self.customer_id}: cannot renew a cancelled subscription")
        self.period_start = self.period_end
        self.period_end = add_month(self.period_end, self.anchor_day)

    def cancel(self) -> None:
        self.status = Status.CANCELLED
