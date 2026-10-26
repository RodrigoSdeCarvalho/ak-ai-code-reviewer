"""Invoices and the settlement job that charges them."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum

from billing.gateway import GatewayError, PaymentGateway
from billing.retry import RetryingGateway, RetryPolicy

logger = logging.getLogger(__name__)


class InvoiceStatus(str, Enum):
    OPEN = "open"
    PAID = "paid"
    PAYMENT_FAILED = "payment_failed"


@dataclass
class Invoice:
    id: int
    customer_id: str
    amount_cents: int
    currency: str = "EUR"
    status: InvoiceStatus = InvoiceStatus.OPEN
    charge_id: str | None = None
    failure_reason: str | None = None


def settle_invoice(gateway: PaymentGateway, invoice: Invoice) -> Invoice:
    """Charge an open invoice and record the outcome on it."""
    if invoice.status is not InvoiceStatus.OPEN:
        raise ValueError(f"invoice {invoice.id} is {invoice.status.value}, not open")
    try:
        charge = gateway.charge(
            invoice.customer_id,
            invoice.amount_cents,
            invoice.currency,
            idempotency_key=f"invoice-{invoice.id}",
        )
    except GatewayError as exc:
        logger.info("invoice %s not settled: %s", invoice.id, exc)
        invoice.status = InvoiceStatus.PAYMENT_FAILED
        invoice.failure_reason = str(exc)
        return invoice
    invoice.status = InvoiceStatus.PAID
    invoice.charge_id = charge.id
    return invoice


def settle_open_invoices(
    gateway: PaymentGateway,
    invoices: Iterable[Invoice],
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Settle every open invoice, retrying failed charges per `policy`, and count the outcomes."""
    retrying = RetryingGateway(gateway, policy, sleep)
    counts = {"paid": 0, "failed": 0}
    for invoice in invoices:
        if invoice.status is not InvoiceStatus.OPEN:
            continue
        settle_invoice(retrying, invoice)
        counts["paid" if invoice.status is InvoiceStatus.PAID else "failed"] += 1
    return counts
