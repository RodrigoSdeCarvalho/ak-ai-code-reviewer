"""Point-of-sale export records."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("timestamp", "store", "amount")


class RecordError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line


@dataclass(frozen=True)
class Sale:
    day: date
    store: str
    amount_cents: int


def _cents(raw: str, line: int) -> int:
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        raise RecordError(line, f"amount {raw!r} is not a number") from None
    if not amount.is_finite():
        raise RecordError(line, f"amount {raw!r} is not a number")
    if amount != amount.quantize(Decimal("0.01")):
        raise RecordError(line, f"amount {raw!r} has more than two decimals")
    return int(amount * 100)


def read_sales(lines: Iterable[str]) -> Iterator[Sale]:
    """Parse a POS export (CSV with a header row); timestamps are ISO 8601 in store-local time."""
    reader = csv.DictReader(lines)
    missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
    if missing:
        raise RecordError(1, f"missing columns: {', '.join(missing)}")
    for row in reader:
        line = reader.line_num
        if any(row.get(name) is None for name in REQUIRED_COLUMNS):
            raise RecordError(line, "row has fewer columns than the header")
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
        except ValueError:
            raise RecordError(line, f"bad timestamp {row['timestamp']!r}") from None
        yield Sale(stamp.date(), row["store"].strip(), _cents(row["amount"], line))
