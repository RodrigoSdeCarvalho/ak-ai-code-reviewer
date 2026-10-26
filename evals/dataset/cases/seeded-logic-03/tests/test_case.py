from datetime import date

import pytest

from billing.invoices import LineKind, build_invoice
from billing.plans import get_plan
from billing.proration import plan_change_lines, preview_change, prorate
from billing.subscriptions import PlanChange, Subscription

MARCH_11 = date(2026, 3, 11)


def _sub(plan: str = "starter") -> Subscription:
    return Subscription.start("cust-1", get_plan(plan), date(2026, 3, 1))


def _amounts(lines) -> list[int]:
    return [line.amount_cents for line in lines]


def test_credit_covers_the_unused_days_of_the_old_plan():
    # 31-day period, change on day 11: 10 days used, 21 remaining.
    lines = plan_change_lines(_sub(), get_plan("team"), MARCH_11)
    assert _amounts(lines) == [-1016, 4065]
    assert all(line.kind is LineKind.PRORATION for line in lines)


def test_change_plan_bills_the_same_lines_as_the_preview():
    sub = _sub()
    expected = plan_change_lines(sub, get_plan("team"), MARCH_11)
    assert sub.change_plan(get_plan("team"), MARCH_11) == expected
    assert sub.plan.code == "team"
    assert sub.history == [PlanChange(MARCH_11, "starter", "team")]


def test_change_outside_the_period_leaves_the_subscription_untouched():
    sub = _sub()
    with pytest.raises(ValueError):
        sub.change_plan(get_plan("team"), date(2026, 4, 5))
    assert sub.plan.code == "starter"
    assert sub.history == []
    assert sub.pending_lines == []


def test_next_invoice_carries_the_adjustment_and_the_new_plan():
    sub = _sub()
    sub.change_plan(get_plan("team"), MARCH_11)
    sub.renew()
    invoice = build_invoice(sub)
    assert _amounts(invoice.lines) == [-1016, 4065, 6000]
    assert (invoice.subtotal_cents, invoice.tax_cents, invoice.total_cents) == (9049, 1810, 10859)
    assert (invoice.period_start, invoice.period_end) == (date(2026, 4, 1), date(2026, 5, 1))
    assert sub.pending_lines == []
    assert _amounts(build_invoice(sub).lines) == [6000]


def test_downgrade_preview_and_change_on_the_first_day():
    sub = _sub("business")
    assert preview_change(sub, get_plan("starter"), MARCH_11) == (
        "Switching to Starter on 2026-03-11: credit of 152.42 before tax"
    )
    assert _amounts(_sub().change_plan(get_plan("team"), date(2026, 3, 1))) == [-1500, 6000]


def test_prorate_and_validation():
    assert prorate(1000, 15, 30) == 500
    assert prorate(1, 1, 2) == 1
    with pytest.raises(ValueError):
        prorate(1000, 31, 30)
    with pytest.raises(ValueError):
        _sub().change_plan(get_plan("starter"), MARCH_11)
