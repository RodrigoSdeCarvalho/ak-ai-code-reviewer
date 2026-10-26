"""Payload for the back-office orders dashboard."""

from __future__ import annotations

import sqlite3
from datetime import date

from reports.orders_report import OrderRow, orders_between, revenue_cents, top_customers


def format_cents(cents: int) -> str:
    """Render a non-negative amount in cents as `units.cents`."""
    return f"{cents // 100}.{cents % 100:02d}"


def _row_payload(row: OrderRow) -> dict[str, object]:
    return {
        "id": row.order_id,
        "customer": row.customer,
        "status": row.status,
        "total": format_cents(row.total_cents),
        "placed_on": row.placed_on.isoformat(),
    }


def orders_panel(conn: sqlite3.Connection, start: date, end: date) -> dict[str, object]:
    """Orders, revenue and top customers for the selected date range."""
    if end < start:
        raise ValueError("end date is before start date")
    rows = orders_between(conn, start, end)
    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(rows),
        "revenue": format_cents(revenue_cents(rows)),
        "top_customers": [
            {"customer": name, "spend": format_cents(cents)} for name, cents in top_customers(rows)
        ],
        "orders": [_row_payload(r) for r in rows],
    }
