"""Payload for the back-office orders dashboard."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
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


def orders_panel(
    conn: sqlite3.Connection,
    start: date,
    end: date,
    *,
    statuses: Sequence[str] | None = None,
    sort: str = "placed",
    descending: bool = True,
) -> dict[str, object]:
    """Orders, revenue and top customers for the selected date range and statuses."""
    if end < start:
        raise ValueError("end date is before start date")
    rows = orders_between(conn, start, end, statuses=statuses, sort=sort, descending=descending)
    return {
        "range": {"start": start.isoformat(), "end": end.isoformat()},
        "count": len(rows),
        "revenue": format_cents(revenue_cents(rows)),
        "top_customers": [
            {"customer": name, "spend": format_cents(cents)} for name, cents in top_customers(rows)
        ],
        "orders": [_row_payload(r) for r in rows],
    }


def panel_from_query(conn: sqlite3.Connection, query: Mapping[str, str]) -> dict[str, object]:
    """Build the panel from dashboard query parameters.

    `start` and `end` are ISO dates, `status` is a comma-separated list of statuses and
    `sort` names a sortable column, prefixed with `-` for descending (default `-placed`).
    """
    missing = [key for key in ("start", "end") if key not in query]
    if missing:
        raise ValueError(f"missing query parameter: {', '.join(missing)}")
    start = date.fromisoformat(query["start"])
    end = date.fromisoformat(query["end"])
    raw_status = query.get("status", "")
    statuses = [s.strip() for s in raw_status.split(",") if s.strip()] or None
    sort = query.get("sort", "-placed")
    descending = sort.startswith("-")
    return orders_panel(conn, start, end, statuses=statuses, sort=sort.removeprefix("-"), descending=descending)
