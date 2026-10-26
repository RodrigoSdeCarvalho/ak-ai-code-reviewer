import io
import json
from datetime import date, datetime, timedelta

from adserve.ledger import JsonlImpressionLog
from adserve.model import BidRequest, Campaign, Impression
from adserve.pacing import BudgetPacer
from adserve.report import format_report, spend_report, write_csv

DAY = date(2026, 3, 9)

SHOES = Campaign("c-shoes", "Trailhead Shoes", daily_budget_micros=2_400_000_000, max_bid_micros=2_000_000)
TEA = Campaign(
    "c-tea",
    "Leaf & Kettle",
    daily_budget_micros=480_000_000,
    max_bid_micros=1_500_000,
    hourly_cap_micros=30_000_000,
)
BANK = Campaign("c-bank", "Northshore Bank", daily_budget_micros=1_200_000_000, max_bid_micros=3_000_000)
PAUSED = Campaign("c-old", "Retired Brand", daily_budget_micros=100_000_000, max_bid_micros=5_000_000, active=False)
CAMPAIGNS = [SHOES, TEA, BANK, PAUSED]


class CountingLog:
    def __init__(self) -> None:
        self.impressions: list[Impression] = []
        self.invalid: set[str] = set()
        self.reads = 0

    def append(self, impression: Impression) -> None:
        self.impressions.append(impression)

    def mark_invalid(self, impression: Impression) -> None:
        self.invalid.add(impression.impression_id)

    def for_day(self, campaign_id: str, day: date) -> list[Impression]:
        self.reads += 1
        return [
            impression
            for impression in self.impressions
            if impression.campaign_id == campaign_id
            and impression.served_at.date() == day
            and impression.impression_id not in self.invalid
        ]


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, 9, hour, minute)


def _request(number: int, at: datetime, floor: int = 100_000) -> BidRequest:
    return BidRequest(f"r{number}", "home-top", floor, at)


def test_bid_decisions_do_not_reread_the_impression_log():
    log = CountingLog()
    pacer = BudgetPacer(CAMPAIGNS, log)
    served = 0
    for number in range(600):
        at = _at(9) + timedelta(seconds=6 * number)
        winners = pacer.eligible(_request(number, at))
        if winners:
            pacer.record(Impression(f"i{number}", winners[0].campaign_id, 1_000_000, at))
            served += 1
    assert served == 600
    assert log.reads <= 3


def test_daily_pacing_and_hourly_cap():
    log = CountingLog()
    pacer = BudgetPacer(CAMPAIGNS, log, slack=0.0)
    pacer.record(Impression("s1", "c-shoes", 598_000_000, _at(5)))
    assert not pacer.can_bid(SHOES, _request(1, _at(5, 59)))
    assert pacer.can_bid(SHOES, _request(2, _at(6)))

    for number in range(14):
        pacer.record(Impression(f"t{number}", "c-tea", 2_000_000, _at(12, number)))
    assert pacer.can_bid(TEA, _request(3, _at(12, 30)))
    pacer.record(Impression("t14", "c-tea", 2_000_000, _at(12, 31)))
    assert not pacer.can_bid(TEA, _request(4, _at(12, 40)))
    assert pacer.can_bid(TEA, _request(5, _at(13)))


def test_floor_and_paused_campaigns_are_not_eligible():
    pacer = BudgetPacer(CAMPAIGNS, CountingLog())
    eligible = pacer.eligible(_request(1, _at(10), floor=2_500_000))
    assert [campaign.campaign_id for campaign in eligible] == ["c-bank"]


def test_refunded_impressions_stop_counting():
    log = CountingLog()
    pacer = BudgetPacer(CAMPAIGNS, log, slack=0.0)
    invalid = [Impression(f"x{number}", "c-tea", 3_000_000, _at(10, number)) for number in range(10)]
    for impression in invalid:
        pacer.record(impression)
    assert not pacer.can_bid(TEA, _request(1, _at(10, 20)))
    for impression in invalid[:5]:
        pacer.refund(impression)
    assert pacer.can_bid(TEA, _request(2, _at(10, 21)))
    assert pacer.spend("c-tea", DAY).total == 15_000_000


def test_restarted_pacer_continues_from_the_log():
    log = CountingLog()
    first = BudgetPacer(CAMPAIGNS, log, slack=0.0)
    first.record(Impression("b1", "c-bank", 299_000_000, _at(5)))
    second = BudgetPacer(CAMPAIGNS, log, slack=0.0)
    assert not second.can_bid(BANK, _request(1, _at(6)))
    assert second.can_bid(BANK, _request(2, _at(6, 4)))


def test_jsonl_log_round_trip_and_invalid_records(tmp_path):
    log = JsonlImpressionLog(tmp_path)
    kept = Impression("j1", "c-tea", 1_250_000, _at(8, 15))
    dropped = Impression("j2", "c-tea", 900_000, _at(8, 16))
    other = Impression("j3", "c-bank", 2_000_000, _at(8, 17))
    for impression in (kept, dropped, other):
        log.append(impression)
    log.mark_invalid(dropped)
    legacy = {"id": "j0", "campaign": "c-tea", "cost": 500_000, "at": _at(7).isoformat()}
    with (tmp_path / "impressions-2026-03-09.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(legacy) + "\n")
    assert [impression.impression_id for impression in log.for_day("c-tea", DAY)] == ["j1", "j0"]
    assert log.for_day("c-tea", date(2026, 3, 10)) == []


def test_spend_report_rows_text_and_csv():
    log = CountingLog()
    pacer = BudgetPacer(CAMPAIGNS, log)
    pacer.record(Impression("a", "c-tea", 120_000_000, _at(11)))
    pacer.record(Impression("b", "c-tea", 24_000_000, _at(14)))
    pacer.record(Impression("c", "c-shoes", 600_000_000, _at(9)))
    rows = spend_report(pacer, DAY)
    assert [(row.campaign_id, row.spent_micros, row.peak_hour) for row in rows] == [
        ("c-tea", 144_000_000, 11),
        ("c-shoes", 600_000_000, 9),
        ("c-bank", 0, None),
        ("c-old", 0, None),
    ]
    text = format_report(rows, DAY).splitlines()
    assert text[0] == "Spend for 2026-03-09"
    assert text[1].startswith("Leaf & Kettle  ")
    assert text[1].endswith("30.0%  peak 11:00")
    assert text[3].endswith("0.0%  no spend")
    out = io.StringIO()
    write_csv(rows, out)
    assert out.getvalue().splitlines()[1] == "c-tea,Leaf & Kettle,144.00,480.00,0.3000,11"
