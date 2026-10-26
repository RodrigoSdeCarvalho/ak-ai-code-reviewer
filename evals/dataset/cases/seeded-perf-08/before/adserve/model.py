from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MICROS_PER_UNIT = 1_000_000


def format_micros(micros: int) -> str:
    return f"{micros / MICROS_PER_UNIT:,.2f}"


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    advertiser: str
    daily_budget_micros: int
    max_bid_micros: int
    active: bool = True


@dataclass(frozen=True)
class Impression:
    impression_id: str
    campaign_id: str
    cost_micros: int
    served_at: datetime


@dataclass(frozen=True)
class BidRequest:
    request_id: str
    placement: str
    floor_micros: int
    received_at: datetime
