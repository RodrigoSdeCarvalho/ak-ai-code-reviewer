"""Expense reports and their line items."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    PAID = "paid"


@dataclass(frozen=True)
class Expense:
    """One receipt line. `amount_cents` is the amount in hundredths of one unit of `currency`."""

    id: str
    category: str
    amount_cents: int
    currency: str = "USD"
    has_receipt: bool = False

    def __post_init__(self) -> None:
        if self.amount_cents <= 0:
            raise ValueError(f"{self.id}: amount must be positive")
        if len(self.currency) != 3 or not self.currency.isupper():
            raise ValueError(f"{self.id}: currency must be an ISO 4217 code")


@dataclass
class Report:
    id: str
    employee: str
    expenses: list[Expense] = field(default_factory=list)
    status: Status = Status.DRAFT

    def add(self, expense: Expense) -> None:
        if self.status is not Status.DRAFT:
            raise ValueError(f"report {self.id} is {self.status.value}; only drafts can change")
        if any(existing.id == expense.id for existing in self.expenses):
            raise ValueError(f"report {self.id} already has an expense {expense.id}")
        self.expenses.append(expense)
