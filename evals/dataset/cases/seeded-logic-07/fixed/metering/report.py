"""Monthly usage report with month-over-month change, as a text table or CSV."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from metering.rollup import MonthlyUsage, UsageKey, previous_month

COLUMNS = (
    "account_id",
    "metric",
    "total",
    "active_days",
    "avg_per_day",
    "peak_day",
    "peak_quantity",
    "previous_total",
    "change",
)


@dataclass(frozen=True)
class ReportRow:
    account_id: str
    metric: str
    total: int
    active_days: int
    average_per_day: float
    peak_day: date
    peak_quantity: int
    previous_total: int | None

    @property
    def change_pct(self) -> float | None:
        """Percent change from the previous month, or None when there is nothing to compare."""
        if not self.previous_total:
            return None
        return round((self.total - self.previous_total) / self.previous_total * 100, 1)

    def cells(self) -> list[str]:
        return [
            self.account_id,
            self.metric,
            str(self.total),
            str(self.active_days),
            f"{self.average_per_day:.1f}",
            self.peak_day.isoformat(),
            str(self.peak_quantity),
            "" if self.previous_total is None else str(self.previous_total),
            format_change(self.change_pct),
        ]


def format_change(change_pct: float | None) -> str:
    return "n/a" if change_pct is None else f"{change_pct:+.1f}%"


def build_report(usage: Mapping[UsageKey, MonthlyUsage], month: str) -> list[ReportRow]:
    """One row per account and metric with usage in `month`, sorted by account then metric."""
    prior = previous_month(month)
    rows: list[ReportRow] = []
    for (account_id, metric, row_month), current in usage.items():
        if row_month != month:
            continue
        previous = usage.get((account_id, metric, prior))
        rows.append(
            ReportRow(
                account_id=account_id,
                metric=metric,
                total=current.total,
                active_days=current.active_days,
                average_per_day=current.average_per_active_day,
                peak_day=current.peak_day,
                peak_quantity=current.peak_quantity,
                previous_total=previous.total if previous is not None else None,
            )
        )
    rows.sort(key=lambda row: (row.account_id, row.metric))
    return rows


def top_accounts(rows: Sequence[ReportRow], metric: str, limit: int = 5) -> list[ReportRow]:
    """The `limit` rows with the highest total for `metric`."""
    matching = [row for row in rows if row.metric == metric]
    return sorted(matching, key=lambda row: (-row.total, row.account_id))[:limit]


def render_text(rows: Sequence[ReportRow], month: str) -> str:
    """Fixed-width table with a title line."""
    table = [list(COLUMNS), *(row.cells() for row in rows)]
    widths = [max(len(line[index]) for line in table) for index in range(len(COLUMNS))]
    lines = [f"Usage report for {month}", ""]
    for line in table:
        lines.append("  ".join(cell.ljust(width) for cell, width in zip(line, widths)).rstrip())
    if not rows:
        lines.append("(no usage)")
    return "\n".join(lines) + "\n"


def render_csv(rows: Sequence[ReportRow]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(row.cells() for row in rows)
    return buffer.getvalue()
