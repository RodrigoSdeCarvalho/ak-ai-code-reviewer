"""Company expense policy."""

from __future__ import annotations

from expenses.models import Report

LIMITS_CENTS = {"meals": 7_500, "lodging": 30_000, "travel": 150_000}
DEFAULT_LIMIT_CENTS = 20_000
RECEIPT_REQUIRED_FROM_CENTS = 2_500


def limit_for(category: str) -> int:
    """Per-expense limit for `category`, in US cents."""
    return LIMITS_CENTS.get(category, DEFAULT_LIMIT_CENTS)


def check(report: Report) -> bool:
    """True when every expense is within its category limit and has a receipt where one is required."""
    for expense in report.expenses:
        if expense.amount_cents > limit_for(expense.category):
            return False
        if expense.amount_cents >= RECEIPT_REQUIRED_FROM_CENTS and not expense.has_receipt:
            return False
    return True
