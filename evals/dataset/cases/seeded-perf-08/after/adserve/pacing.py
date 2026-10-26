from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time

from adserve.ledger import ImpressionLog
from adserve.model import BidRequest, Campaign, Impression

SECONDS_PER_DAY = 24 * 60 * 60


def day_fraction(now: datetime) -> float:
    midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    return (now - midnight).total_seconds() / SECONDS_PER_DAY


@dataclass(frozen=True)
class Spend:
    campaign_id: str
    day: date
    hourly: tuple[int, ...]

    @property
    def total(self) -> int:
        return sum(self.hourly)

    def in_hour(self, hour: int) -> int:
        return self.hourly[hour]


class BudgetPacer:
    """Spreads each campaign's daily budget evenly over the day.

    A campaign may bid while its spend so far plus its maximum bid stays within the share of the daily
    budget that matches the time of day, plus some slack so it can catch up after quiet hours, and within
    its hourly cap if it has one.

    Spend comes from the impression log, so pacing carries on where it left off after a restart and
    impressions credited back as invalid traffic stop counting against the budget.
    """

    def __init__(self, campaigns: Iterable[Campaign], log: ImpressionLog, *, slack: float = 0.05) -> None:
        self._campaigns = {campaign.campaign_id: campaign for campaign in campaigns}
        self._log = log
        self._slack = slack

    @property
    def campaigns(self) -> list[Campaign]:
        return list(self._campaigns.values())

    def record(self, impression: Impression) -> None:
        self._log.append(impression)

    def refund(self, impression: Impression) -> None:
        self._log.mark_invalid(impression)

    def spend(self, campaign_id: str, day: date) -> Spend:
        hourly = [0] * 24
        for impression in self._log.for_day(campaign_id, day):
            hourly[impression.served_at.hour] += impression.cost_micros
        return Spend(campaign_id, day, tuple(hourly))

    def allowance(self, campaign: Campaign, now: datetime) -> int:
        share = min(1.0, day_fraction(now) + self._slack)
        return int(campaign.daily_budget_micros * share)

    def can_bid(self, campaign: Campaign, request: BidRequest) -> bool:
        if not campaign.active or campaign.max_bid_micros < request.floor_micros:
            return False
        now = request.received_at
        spend = self.spend(campaign.campaign_id, now.date())
        if spend.total + campaign.max_bid_micros > self.allowance(campaign, now):
            return False
        cap = campaign.hourly_cap_micros
        return cap is None or spend.in_hour(now.hour) + campaign.max_bid_micros <= cap

    def eligible(self, request: BidRequest) -> list[Campaign]:
        return [campaign for campaign in self._campaigns.values() if self.can_bid(campaign, request)]
