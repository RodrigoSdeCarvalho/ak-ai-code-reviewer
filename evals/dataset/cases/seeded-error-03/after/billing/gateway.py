"""Payment gateway client interface and the errors it raises."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class GatewayError(Exception):
    """Base class for every error reported by the payment gateway."""


class CardDeclined(GatewayError):
    """The card issuer refused the charge."""

    def __init__(self, decline_code: str) -> None:
        super().__init__(f"card declined ({decline_code})")
        self.decline_code = decline_code


class InvalidRequest(GatewayError):
    """The gateway rejected the request itself (bad currency, amount, customer)."""


class GatewayUnavailable(GatewayError):
    """The gateway could not be reached or answered 5xx. Safe to retry with the same idempotency key."""


class GatewayTimeout(GatewayError):
    """No answer in time. Safe to retry with the same idempotency key."""


@dataclass(frozen=True)
class Charge:
    id: str
    customer_id: str
    amount_cents: int
    currency: str


class PaymentGateway(Protocol):
    def charge(
        self, customer_id: str, amount_cents: int, currency: str, idempotency_key: str
    ) -> Charge:
        """Charge the customer's default card.

        Two calls with the same idempotency key create at most one charge.
        """
        ...
