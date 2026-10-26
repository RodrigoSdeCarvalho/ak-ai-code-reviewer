"""A small connection pool over an in-process table store."""

from __future__ import annotations

import threading
from copy import deepcopy
from typing import Any

Row = dict[str, Any]


class PoolExhausted(RuntimeError):
    """Raised when every connection in the pool is checked out."""


class Store:
    """Tables of rows keyed by primary key, shared by every connection."""

    def __init__(self) -> None:
        self.tables: dict[str, dict[str, Row]] = {}
        self.lock = threading.Lock()


class Connection:
    """A connection with one pending transaction; writes become visible on commit."""

    def __init__(self, store: Store) -> None:
        self._store = store
        self._pending: dict[tuple[str, str], Row | None] = {}

    def get(self, table: str, key: str) -> Row | None:
        if (table, key) in self._pending:
            row = self._pending[(table, key)]
        else:
            with self._store.lock:
                row = self._store.tables.get(table, {}).get(key)
        return deepcopy(row) if row is not None else None

    def put(self, table: str, key: str, row: Row) -> None:
        self._pending[(table, key)] = deepcopy(row)

    def delete(self, table: str, key: str) -> None:
        self._pending[(table, key)] = None

    def commit(self) -> None:
        with self._store.lock:
            for (table, key), row in self._pending.items():
                rows = self._store.tables.setdefault(table, {})
                if row is None:
                    rows.pop(key, None)
                else:
                    rows[key] = row
        self._pending.clear()

    def rollback(self) -> None:
        self._pending.clear()


class ConnectionPool:
    """A fixed number of connections handed out with acquire() and returned with release()."""

    def __init__(self, store: Store, size: int = 4) -> None:
        self.size = size
        self._idle = [Connection(store) for _ in range(size)]
        self._lock = threading.Lock()

    @property
    def available(self) -> int:
        with self._lock:
            return len(self._idle)

    def acquire(self) -> Connection:
        with self._lock:
            if not self._idle:
                raise PoolExhausted(f"all {self.size} connections are in use")
            return self._idle.pop()

    def release(self, conn: Connection) -> None:
        conn.rollback()
        with self._lock:
            self._idle.append(conn)
