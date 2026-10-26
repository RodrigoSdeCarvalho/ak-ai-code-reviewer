"""Retry wrapper for the payment gateway."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from billing.gateway import Charge, GatewayTimeout, GatewayUnavailable, PaymentGateway

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("attempts must be >= 1")
        if self.base_delay < 0 or self.max_delay < self.base_delay:
            raise ValueError("delays must satisfy 0 <= base_delay <= max_delay")

    def delay(self, attempt: int) -> float:
        """Seconds to wait after failed attempt number `attempt` (1-based)."""
        return min(self.base_delay * 2 ** (attempt - 1), self.max_delay)


class RetryingGateway:
    """A PaymentGateway that retries failed charges with exponential backoff.

    Every attempt reuses the caller's idempotency key, so a retried charge is never applied twice.
    """

    def __init__(
        self,
        gateway: PaymentGateway,
        policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._gateway = gateway
        self._policy = policy or RetryPolicy()
        self._sleep = sleep

    def charge(
        self, customer_id: str, amount_cents: int, currency: str, idempotency_key: str
    ) -> Charge:
        attempts = self._policy.attempts
        for attempt in range(1, attempts + 1):
            try:
                return self._gateway.charge(customer_id, amount_cents, currency, idempotency_key)
            except (GatewayUnavailable, GatewayTimeout) as exc:
                logger.warning(
                    "charge %s failed (attempt %d/%d): %s", idempotency_key, attempt, attempts, exc
                )
                if attempt == attempts:
                    logger.error("giving up on charge %s", idempotency_key)
                    raise
                self._sleep(self._policy.delay(attempt))
