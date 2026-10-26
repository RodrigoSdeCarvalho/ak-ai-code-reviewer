"""Customer subscriptions billed monthly in advance."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from billing.invoices import LineItem
from billing.plans import Plan
from billing.proration import plan_change_lines


class Status(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


def add_month(day: date, anchor_day: int) -> date:
    """The date one month after `day`, on `anchor_day` or the last day of a shorter month."""
    year, month = (day.year + 1, 1) if day.month == 12 else (day.year, day.month + 1)
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor_day, last))


@dataclass(frozen=True)
class PlanChange:
    on: date
    from_code: str
    to_code: str


@dataclass
class Subscription:
    """A subscription whose current billing period is [period_start, period_end).

    Plan changes take effect immediately; their prorated credit and charge are held in
    `pending_lines` until the next invoice is built.
    """

    customer_id: str
    plan: Plan
    period_start: date
    period_end: date
    anchor_day: int
    status: Status = Status.ACTIVE
    history: list[PlanChange] = field(default_factory=list)
    pending_lines: list[LineItem] = field(default_factory=list)

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

    def change_plan(self, new_plan: Plan, on: date) -> list[LineItem]:
        """Switch to `new_plan` from `on` and queue the prorated adjustment for the next invoice."""
        if self.status is not Status.ACTIVE:
            raise ValueError(f"{self.customer_id}: cannot change the plan of a cancelled subscription")
        if new_plan.code == self.plan.code:
            raise ValueError(f"{self.customer_id}: already on {new_plan.code}")
        previous = self.plan
        self.plan = new_plan
        self.history.append(PlanChange(on, previous.code, new_plan.code))
        adjustment = plan_change_lines(self, new_plan, on)
        self.pending_lines.extend(adjustment)
        return adjustment

    def take_pending_lines(self) -> list[LineItem]:
        """Return the queued adjustment lines and clear the queue."""
        lines, self.pending_lines = self.pending_lines, []
        return lines
