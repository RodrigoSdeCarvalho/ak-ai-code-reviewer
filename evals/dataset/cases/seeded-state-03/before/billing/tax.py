"""Sales tax rates by jurisdiction and tax lines for invoices."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Protocol

CENT = Decimal("0.01")


class UnknownJurisdiction(LookupError):
    pass


class RateSource(Protocol):
    def rate_for(self, country: str, postal_code: str) -> Decimal: ...


class TableRateSource:
    """Rates from a table per country, matched on the longest postal-code prefix, then `*`."""

    def __init__(self, rates: dict[str, dict[str, Decimal]]) -> None:
        self._rates = {country: dict(table) for country, table in rates.items()}
        self.lookups = 0

    def rate_for(self, country: str, postal_code: str) -> Decimal:
        self.lookups += 1
        table = self._rates.get(country)
        if table is None:
            raise UnknownJurisdiction(country)
        for length in range(len(postal_code), 0, -1):
            rate = table.get(postal_code[:length])
            if rate is not None:
                return rate
        if "*" in table:
            return table["*"]
        raise UnknownJurisdiction(f"{country} {postal_code}")

    def replace_country(self, country: str, table: dict[str, Decimal]) -> None:
        self._rates[country] = dict(table)


@dataclass(frozen=True)
class TaxLine:
    description: str
    net: Decimal
    rate: Decimal
    tax: Decimal


def normalise_postal_code(postal_code: str) -> str:
    return postal_code.replace(" ", "").replace("-", "").upper()


class TaxCalculator:
    def __init__(self, source: RateSource) -> None:
        self._source = source
        self._lookup = lru_cache(maxsize=4096)(source.rate_for)

    def rate(self, country: str, postal_code: str) -> Decimal:
        return self._lookup(country.upper(), normalise_postal_code(postal_code))

    def tax_lines(
        self, country: str, postal_code: str, items: list[tuple[str, Decimal]]
    ) -> list[TaxLine]:
        rate = self.rate(country, postal_code)
        return [
            TaxLine(description, net, rate, (net * rate).quantize(CENT, ROUND_HALF_UP))
            for description, net in items
        ]

    def clear_cache(self) -> None:
        self._lookup.cache_clear()
