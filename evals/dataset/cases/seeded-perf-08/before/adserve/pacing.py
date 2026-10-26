from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, time

from adserve.ledger import ImpressionLog
from adserve.model import BidRequest, Campaign, Impression

SECONDS_PER_DAY = 24 * 60 * 60


def day_fraction(now: datetime) -> float:
    midnight = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    return (now - midnight).total_seconds() / SECONDS_PER_DAY


class BudgetPacer:
    """Spreads each campaign's daily budget evenly over the day.

    A campaign may bid while its spend so far plus its maximum bid stays within the share of the daily
    budget that matches the time of day, plus some slack so it can catch up after quiet hours.
    """

    def __init__(self, campaigns: Iterable[Campaign], log: ImpressionLog, *, slack: float = 0.05) -> None:
        self._campaigns = {campaign.campaign_id: campaign for campaign in campaigns}
        self._log = log
        self._slack = slack
        self._day: date | None = None
        self._spent: dict[str, int] = {}

    def _roll(self, day: date) -> None:
        if self._day is None or day > self._day:
            self._day = day
            self._spent = {}

    def record(self, impression: Impression) -> None:
        self._log.append(impression)
        day = impression.served_at.date()
        self._roll(day)
        if day == self._day:
            campaign_id = impression.campaign_id
            self._spent[campaign_id] = self._spent.get(campaign_id, 0) + impression.cost_micros

    def allowance(self, campaign: Campaign, now: datetime) -> int:
        share = min(1.0, day_fraction(now) + self._slack)
        return int(campaign.daily_budget_micros * share)

    def can_bid(self, campaign: Campaign, request: BidRequest) -> bool:
        if not campaign.active or campaign.max_bid_micros < request.floor_micros:
            return False
        self._roll(request.received_at.date())
        spent = self._spent.get(campaign.campaign_id, 0)
        return spent + campaign.max_bid_micros <= self.allowance(campaign, request.received_at)

    def eligible(self, request: BidRequest) -> list[Campaign]:
        return [campaign for campaign in self._campaigns.values() if self.can_bid(campaign, request)]
