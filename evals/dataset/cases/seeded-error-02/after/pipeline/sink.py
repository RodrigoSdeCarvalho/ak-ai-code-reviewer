"""Destinations that loaded transactions are written to."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from pipeline.parse import Transaction


class SinkError(RuntimeError):
    """The destination could not accept a batch."""


class Sink(Protocol):
    def write(self, batch: Sequence[Transaction]) -> None:
        """Persist `batch` as a unit, or raise SinkError and persist nothing."""
        ...


class MemorySink:
    """Keeps written batches in memory; used by tests and dry runs."""

    def __init__(self, capacity: int | None = None) -> None:
        self.rows: list[Transaction] = []
        self.batches = 0
        self._capacity = capacity

    def write(self, batch: Sequence[Transaction]) -> None:
        if self._capacity is not None and len(self.rows) + len(batch) > self._capacity:
            raise SinkError(f"capacity {self._capacity} exceeded")
        self.rows.extend(batch)
        self.batches += 1

    def __len__(self) -> int:
        return len(self.rows)

    def accounts(self) -> set[str]:
        return {row.account for row in self.rows}

    def total(self, currency: str) -> Decimal:
        return sum((row.amount for row in self.rows if row.currency == currency), start=Decimal(0))

    def clear(self) -> None:
        self.rows.clear()
        self.batches = 0
