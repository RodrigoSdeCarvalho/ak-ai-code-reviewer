"""SQLite access for the reporting service."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL,
    status TEXT NOT NULL,
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    placed_on TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_placed_on ON orders (placed_on);
"""


@dataclass(frozen=True)
class NewOrder:
    customer: str
    status: str
    total_cents: int
    placed_on: date


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open the reporting database with rows addressable by column name."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_orders(conn: sqlite3.Connection, orders: Iterable[NewOrder]) -> list[int]:
    """Insert orders in one transaction and return their ids in input order."""
    ids: list[int] = []
    with conn:
        for order in orders:
            cursor = conn.execute(
                "INSERT INTO orders (customer, status, total_cents, placed_on) VALUES (?, ?, ?, ?)",
                (order.customer, order.status, order.total_cents, order.placed_on.isoformat()),
            )
            ids.append(int(cursor.lastrowid))
    return ids
