import pytest

from billing.gateway import (
    CardDeclined,
    Charge,
    GatewayTimeout,
    GatewayUnavailable,
    InvalidRequest,
)
from billing.invoices import Invoice, InvoiceStatus, settle_open_invoices
from billing.retry import RetryingGateway, RetryPolicy


class ScriptedGateway:
    """Plays back a list of outcomes per idempotency key; succeeds once a script runs out."""

    def __init__(self, scripts: dict[str, list[Exception]] | None = None) -> None:
        self._scripts = {key: list(errors) for key, errors in (scripts or {}).items()}
        self.calls: list[str] = []

    def charge(self, customer_id, amount_cents, currency, idempotency_key):
        self.calls.append(idempotency_key)
        script = self._scripts.get(idempotency_key, [])
        if script:
            raise script.pop(0)
        return Charge(f"ch_{idempotency_key}", customer_id, amount_cents, currency)


def _retrying(gateway, sleeps):
    return RetryingGateway(gateway, RetryPolicy(attempts=3, base_delay=0.5), sleeps.append)


def test_transient_errors_are_retried_with_backoff():
    sleeps: list[float] = []
    gateway = ScriptedGateway({"k1": [GatewayUnavailable("502"), GatewayTimeout("30s")]})
    charge = _retrying(gateway, sleeps).charge("cus_1", 1500, "EUR", "k1")
    assert charge.id == "ch_k1"
    assert gateway.calls == ["k1", "k1", "k1"]
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize("error", [CardDeclined("insufficient_funds"), InvalidRequest("bad currency")])
def test_permanent_errors_are_not_retried(error):
    sleeps: list[float] = []
    gateway = ScriptedGateway({"k1": [error]})
    with pytest.raises(type(error)):
        _retrying(gateway, sleeps).charge("cus_1", 1500, "EUR", "k1")
    assert gateway.calls == ["k1"]
    assert sleeps == []


def test_last_transient_error_is_raised_when_attempts_run_out():
    sleeps: list[float] = []
    gateway = ScriptedGateway({"k1": [GatewayUnavailable("503")] * 5})
    with pytest.raises(GatewayUnavailable):
        _retrying(gateway, sleeps).charge("cus_1", 1500, "EUR", "k1")
    assert gateway.calls == ["k1"] * 3
    assert sleeps == [0.5, 1.0]


def test_settlement_marks_unreachable_gateway_as_failed_and_continues():
    invoices = [Invoice(1, "cus_1", 1000), Invoice(2, "cus_2", 2500)]
    gateway = ScriptedGateway({"invoice-1": [GatewayUnavailable("503")] * 3})
    counts = settle_open_invoices(gateway, invoices, sleep=lambda _: None)
    assert counts == {"paid": 1, "failed": 1}
    assert invoices[0].status is InvoiceStatus.PAYMENT_FAILED
    assert invoices[1].status is InvoiceStatus.PAID
    assert invoices[1].charge_id == "ch_invoice-2"


def test_settlement_charges_a_declined_card_once():
    invoices = [Invoice(1, "cus_1", 1000)]
    gateway = ScriptedGateway({"invoice-1": [CardDeclined("do_not_honor")] * 3})
    counts = settle_open_invoices(gateway, invoices, sleep=lambda _: None)
    assert gateway.calls == ["invoice-1"]
    assert counts == {"paid": 0, "failed": 1}
    assert invoices[0].failure_reason == "card declined (do_not_honor)"
