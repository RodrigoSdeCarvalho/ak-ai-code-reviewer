from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from typing import TextIO

from adserve.model import MICROS_PER_UNIT, format_micros
from adserve.pacing import BudgetPacer


@dataclass(frozen=True)
class SpendRow:
    campaign_id: str
    advertiser: str
    spent_micros: int
    budget_micros: int
    peak_hour: int | None
    peak_micros: int

    @property
    def utilisation(self) -> float:
        return self.spent_micros / self.budget_micros if self.budget_micros else 0.0


def spend_report(pacer: BudgetPacer, day: date) -> list[SpendRow]:
    rows: list[SpendRow] = []
    for campaign in pacer.campaigns:
        spend = pacer.spend(campaign.campaign_id, day)
        peak_micros = max(spend.hourly)
        rows.append(
            SpendRow(
                campaign_id=campaign.campaign_id,
                advertiser=campaign.advertiser,
                spent_micros=spend.total,
                budget_micros=campaign.daily_budget_micros,
                peak_hour=spend.hourly.index(peak_micros) if peak_micros else None,
                peak_micros=peak_micros,
            )
        )
    rows.sort(key=lambda row: (-row.utilisation, row.campaign_id))
    return rows


def format_report(rows: list[SpendRow], day: date) -> str:
    header = f"Spend for {day.isoformat()}"
    if not rows:
        return f"{header}\nno campaigns"
    width = max(len(row.advertiser) for row in rows)
    lines = [header]
    for row in rows:
        peak = f"peak {row.peak_hour:02d}:00" if row.peak_hour is not None else "no spend"
        amounts = f"{format_micros(row.spent_micros):>12} / {format_micros(row.budget_micros):>12}"
        lines.append(f"{row.advertiser.ljust(width)}  {amounts}  {row.utilisation:7.1%}  {peak}")
    return "\n".join(lines)


def write_csv(rows: list[SpendRow], out: TextIO) -> None:
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["campaign_id", "advertiser", "spent", "budget", "utilisation", "peak_hour"])
    for row in rows:
        writer.writerow(
            [
                row.campaign_id,
                row.advertiser,
                f"{row.spent_micros / MICROS_PER_UNIT:.2f}",
                f"{row.budget_micros / MICROS_PER_UNIT:.2f}",
                f"{row.utilisation:.4f}",
                "" if row.peak_hour is None else row.peak_hour,
            ]
        )
