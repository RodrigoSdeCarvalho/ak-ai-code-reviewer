"""Order queries behind the back-office reports."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

SORTABLE_COLUMNS: dict[str, str] = {
    "placed": "placed_on",
    "total": "total_cents",
    "customer": "customer",
}
STATUSES = frozenset({"pending", "paid", "shipped", "refunded"})


@dataclass(frozen=True)
class OrderRow:
    order_id: int
    customer: str
    status: str
    total_cents: int
    placed_on: date


def _to_row(record: sqlite3.Row) -> OrderRow:
    return OrderRow(
        order_id=record["id"],
        customer=record["customer"],
        status=record["status"],
        total_cents=record["total_cents"],
        placed_on=date.fromisoformat(record["placed_on"]),
    )


def orders_between(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    *,
    statuses: Iterable[str] | None = None,
    sort: str = "placed",
    descending: bool = True,
) -> list[OrderRow]:
    """Orders placed from `start` to `end`, both inclusive.

    `sort` is a key of SORTABLE_COLUMNS; ties are broken by order id in the same direction.
    `statuses`, when given, keeps only orders in one of those statuses.
    """
    if sort not in SORTABLE_COLUMNS:
        raise ValueError(f"cannot sort by {sort!r}; choose one of {sorted(SORTABLE_COLUMNS)}")
    column = SORTABLE_COLUMNS[sort]
    direction = "DESC" if descending else "ASC"
    clauses = ["placed_on >= ?", "placed_on <= ?"]
    params: list[str] = [start.isoformat(), end.isoformat()]
    if statuses is not None:
        wanted = sorted(set(statuses))
        unknown = [s for s in wanted if s not in STATUSES]
        if unknown:
            raise ValueError(f"unknown order status: {', '.join(unknown)}")
        if not wanted:
            return []
        clauses.append(f"status IN ({', '.join('?' for _ in wanted)})")
        params.extend(wanted)
    query = (
        "SELECT id, customer, status, total_cents, placed_on FROM orders "
        f"WHERE {' AND '.join(clauses)} ORDER BY {column} {direction}, id {direction}"
    )
    return [_to_row(r) for r in conn.execute(query, params).fetchall()]


def revenue_cents(rows: list[OrderRow]) -> int:
    """Sum of order totals, leaving out refunded orders."""
    return sum(r.total_cents for r in rows if r.status != "refunded")


def top_customers(rows: list[OrderRow], limit: int = 5) -> list[tuple[str, int]]:
    """Customers ranked by non-refunded spend, highest first; ties ordered by name."""
    spend: dict[str, int] = {}
    for row in rows:
        if row.status != "refunded":
            spend[row.customer] = spend.get(row.customer, 0) + row.total_cents
    ranked = sorted(spend.items(), key=lambda item: (-item[1], item[0]))
    return ranked[:limit]
