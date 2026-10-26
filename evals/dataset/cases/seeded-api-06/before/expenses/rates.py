"""Exchange rates from the treasury feed."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal


class UnknownCurrency(KeyError):
    pass


class RateTable:
    """Daily exchange rates quoted against the US dollar.

    The treasury feed publishes, for each currency, how many units of that currency one US dollar
    buys: for example EUR 0.92, GBP 0.79, CAD 1.37.
    """

    def __init__(self, quotes: Mapping[str, Decimal], as_of: date) -> None:
        for code, quote in quotes.items():
            if quote <= 0:
                raise ValueError(f"rate for {code} must be positive")
        self._quotes = dict(quotes)
        self.as_of = as_of

    def per_usd(self, currency: str) -> Decimal:
        """Units of `currency` that one US dollar buys."""
        if currency == "USD":
            return Decimal(1)
        try:
            return self._quotes[currency]
        except KeyError:
            raise UnknownCurrency(currency) from None

    def currencies(self) -> list[str]:
        return sorted({"USD", *self._quotes})
