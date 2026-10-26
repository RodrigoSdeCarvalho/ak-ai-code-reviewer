"""Turn raw CSV rows into validated transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("date", "account", "amount", "currency")
CURRENCIES = frozenset({"EUR", "USD", "GBP", "BRL"})
CENT = Decimal("0.01")


class RowError(ValueError):
    """A row that cannot be turned into a transaction."""


@dataclass(frozen=True)
class Transaction:
    booked_on: date
    account: str
    amount: Decimal
    currency: str
    memo: str


def parse_row(row: dict[str, str]) -> Transaction:
    """Validate one CSV row; every problem is reported as a RowError."""
    missing = [column for column in REQUIRED_COLUMNS if not (row.get(column) or "").strip()]
    if missing:
        raise RowError(f"missing {', '.join(missing)}")
    try:
        booked_on = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
    except ValueError:
        raise RowError(f"bad date {row['date']!r}") from None
    try:
        amount = Decimal(row["amount"].strip().replace(",", "")).quantize(CENT)
    except InvalidOperation:
        raise RowError(f"bad amount {row['amount']!r}") from None
    if not amount.is_finite():
        raise RowError(f"bad amount {row['amount']!r}")
    currency = row["currency"].strip().upper()
    if currency not in CURRENCIES:
        raise RowError(f"unsupported currency {currency!r}")
    return Transaction(
        booked_on=booked_on,
        account=row["account"].strip(),
        amount=amount,
        currency=currency,
        memo=(row.get("memo") or "").strip(),
    )
