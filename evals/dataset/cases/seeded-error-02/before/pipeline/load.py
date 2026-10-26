"""Load parsed transactions into a sink in fixed-size batches."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pipeline.parse import Transaction, parse_row
from pipeline.sink import Sink

DEFAULT_BATCH_SIZE = 500


@dataclass
class LoadReport:
    loaded: int = 0
    batches: int = 0


class Loader:
    def __init__(self, sink: Sink, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self._sink = sink
        self._batch_size = batch_size

    def load(self, rows: Iterable[dict[str, str]]) -> LoadReport:
        """Parse and write every row; the first malformed row aborts the load."""
        report = LoadReport()
        batch: list[Transaction] = []
        for row in rows:
            batch.append(parse_row(row))
            if len(batch) >= self._batch_size:
                self._flush(batch, report)
                batch = []
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
