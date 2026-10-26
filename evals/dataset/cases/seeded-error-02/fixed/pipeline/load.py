"""Load parsed transactions into a sink in fixed-size batches."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from pipeline.parse import RowError, Transaction, parse_row
from pipeline.sink import Sink

DEFAULT_BATCH_SIZE = 500
DEFAULT_MAX_REJECTED = 1000


class TooManyRejected(Exception):
    """More rows were rejected than the loader is allowed to skip."""


@dataclass(frozen=True)
class Rejection:
    row: int
    reason: str


@dataclass
class LoadReport:
    loaded: int = 0
    batches: int = 0
    rejected: list[Rejection] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.rejected


class Loader:
    def __init__(
        self,
        sink: Sink,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_rejected: int = DEFAULT_MAX_REJECTED,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if max_rejected < 0:
            raise ValueError("max_rejected must be >= 0")
        self._sink = sink
        self._batch_size = batch_size
        self._max_rejected = max_rejected

    def load(self, rows: Iterable[dict[str, str]]) -> LoadReport:
        """Parse and write every row, skipping malformed rows and listing them in the report.

        Rejections carry the 1-based data row number (the CSV header is not counted).
        Raises TooManyRejected once more than `max_rejected` rows have been skipped.
        """
        report = LoadReport()
        batch: list[Transaction] = []
        for number, row in enumerate(rows, start=1):
            try:
                batch.append(parse_row(row))
                if len(batch) >= self._batch_size:
                    pending, batch = batch, []
                    self._flush(pending, report)
            except RowError as exc:
                report.rejected.append(Rejection(number, str(exc)))
                if len(report.rejected) > self._max_rejected:
                    raise TooManyRejected(f"{len(report.rejected)} rows rejected") from exc
        if batch:
            self._flush(batch, report)
        return report

    def load_file(self, path: Path) -> LoadReport:
        with path.open(newline="", encoding="utf-8") as fh:
            return self.load(csv.DictReader(fh))

    def _flush(self, batch: list[Transaction], report: LoadReport) -> None:
        self._sink.write(batch)
        report.loaded += len(batch)
        report.batches += 1
