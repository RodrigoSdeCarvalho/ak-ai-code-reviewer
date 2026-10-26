"""Order queries behind the back-office reports."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


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


def orders_between(conn: sqlite3.Connection, start: date, end: date) -> list[OrderRow]:
    """Orders placed from `start` to `end`, both inclusive, newest first."""
    cursor = conn.execute(
        "SELECT id, customer, status, total_cents, placed_on FROM orders "
        "WHERE placed_on >= ? AND placed_on <= ? ORDER BY placed_on DESC, id DESC",
        (start.isoformat(), end.isoformat()),
    )
    return [_to_row(r) for r in cursor.fetchall()]


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
