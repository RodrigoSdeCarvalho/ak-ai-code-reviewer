from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Protocol

from adserve.model import Impression


class ImpressionLog(Protocol):
    def append(self, impression: Impression) -> None: ...

    def mark_invalid(self, impression: Impression) -> None: ...

    def for_day(self, campaign_id: str, day: date) -> list[Impression]: ...


def _impression(record: dict[str, Any]) -> Impression:
    return Impression(
        impression_id=record["id"],
        campaign_id=record["campaign"],
        cost_micros=int(record["cost"]),
        served_at=datetime.fromisoformat(record["at"]),
    )


class JsonlImpressionLog:
    """Append-only impression log, one JSON Lines file per day. Billing reads it back per campaign.

    Impressions found to be invalid traffic are not removed: an ``invalid`` record is appended to the
    file of the day they were served, and reads leave them out.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, day: date) -> Path:
        return self._directory / f"impressions-{day.isoformat()}.jsonl"

    def _write(self, day: date, record: dict[str, Any]) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        with self._path(day).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def append(self, impression: Impression) -> None:
        self._write(
            impression.served_at.date(),
            {
                "id": impression.impression_id,
                "campaign": impression.campaign_id,
                "cost": impression.cost_micros,
                "at": impression.served_at.isoformat(),
            },
        )

    def mark_invalid(self, impression: Impression) -> None:
        self._write(impression.served_at.date(), {"kind": "invalid", "id": impression.impression_id})

    def for_day(self, campaign_id: str, day: date) -> list[Impression]:
        path = self._path(day)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle if line.strip()]
        invalid = {record["id"] for record in records if record.get("kind") == "invalid"}
        return [
            _impression(record)
            for record in records
            if record.get("kind") != "invalid" and record["campaign"] == campaign_id and record["id"] not in invalid
        ]
