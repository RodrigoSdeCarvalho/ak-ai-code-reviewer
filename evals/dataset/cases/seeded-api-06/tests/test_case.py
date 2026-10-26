from datetime import date
from decimal import Decimal

import pytest
from expenses.approval import approve_manually, decide, review_notes, submit
from expenses.models import Expense, Report, Status
from expenses.policy import check, to_usd_cents
from expenses.rates import RateTable

RATES = RateTable({"EUR": Decimal("0.92"), "GBP": Decimal("0.80")}, date(2026, 6, 1))


def _submitted(*expenses: Expense) -> Report:
    report = Report("R-1", "dana")
    for expense in expenses:
        report.add(expense)
    submit(report)
    return report


def test_compliant_report_is_auto_approved():
    report = _submitted(Expense("e1", "meals", 4_200, has_receipt=True), Expense("e2", "travel", 1_800))
    assert decide(report, RATES) is Status.APPROVED


def test_report_over_the_limit_goes_to_a_manager():
    report = _submitted(Expense("e1", "lodging", 41_000, has_receipt=True))
    assert decide(report, RATES) is Status.NEEDS_REVIEW
    assert review_notes(report, RATES) == ["e1: lodging expense of $410.00 is over the $300.00 limit"]
    approve_manually(report, "lee")
    assert report.status is Status.APPROVED


def test_foreign_amounts_are_converted_to_dollars():
    assert to_usd_cents(9_200, "EUR", RATES) == 10_000
    assert to_usd_cents(1_000, "GBP", RATES) == 1_250
    assert to_usd_cents(7_000, "EUR", RATES) == 7_609
    assert to_usd_cents(1_234, "USD", RATES) == 1_234


def test_foreign_meal_over_the_limit_is_flagged():
    report = _submitted(Expense("e1", "meals", 7_000, "EUR", has_receipt=True))
    assert check(report, RATES) == ["e1: meals expense of $76.09 is over the $75.00 limit"]
    assert review_notes(report, RATES)[-1] == "foreign amounts converted at the 2026-06-01 rates"


def test_receipt_threshold_uses_dollar_amount():
    report = _submitted(Expense("e1", "other", 2_200, "GBP"))
    assert check(report, RATES) == ["e1: a receipt is required for $27.50"]
    assert decide(report, RATES) is Status.NEEDS_REVIEW
    with pytest.raises(PermissionError):
        approve_manually(report, "dana")
