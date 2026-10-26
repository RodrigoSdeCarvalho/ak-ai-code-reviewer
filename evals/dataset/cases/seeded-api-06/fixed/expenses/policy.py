"""Company expense policy."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from expenses.models import Report
from expenses.rates import RateTable

LIMITS_CENTS = {"meals": 7_500, "lodging": 30_000, "travel": 150_000}
DEFAULT_LIMIT_CENTS = 20_000
RECEIPT_REQUIRED_FROM_CENTS = 2_500


def limit_for(category: str) -> int:
    """Per-expense limit for `category`, in US cents."""
    return LIMITS_CENTS.get(category, DEFAULT_LIMIT_CENTS)


def to_usd_cents(amount_cents: int, currency: str, rates: RateTable) -> int:
    """Convert `amount_cents` hundredths of `currency` to US cents, rounding half up."""
    converted = Decimal(amount_cents) / rates.per_usd(currency)
    return int(converted.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _dollars(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def check(report: Report, rates: RateTable) -> list[str]:
    """Policy violations in `report`, one message per problem; empty when the report is within policy.

    Foreign-currency expenses are converted to US dollars before they are compared with the limits.
    """
    problems: list[str] = []
    for expense in report.expenses:
        amount = to_usd_cents(expense.amount_cents, expense.currency, rates)
        limit = limit_for(expense.category)
        if amount > limit:
            problems.append(
                f"{expense.id}: {expense.category} expense of {_dollars(amount)} is over the {_dollars(limit)} limit"
            )
        if amount >= RECEIPT_REQUIRED_FROM_CENTS and not expense.has_receipt:
            problems.append(f"{expense.id}: a receipt is required for {_dollars(amount)}")
    return problems
