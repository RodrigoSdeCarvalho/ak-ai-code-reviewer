"""Admin handlers for tax rate tables and rate-cache metrics."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from billing.tax import TableRateSource, TaxCalculator, normalise_postal_code

Response = tuple[int, dict[str, Any]]


def _parse_table(raw: Any) -> dict[str, Decimal]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("rates must be a non-empty object of postal prefix -> rate")
    table: dict[str, Decimal] = {}
    for prefix, value in raw.items():
        try:
            rate = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"rate for {prefix!r} is not a number") from None
        if not rate.is_finite() or not Decimal("0") <= rate < Decimal("1"):
            raise ValueError(f"rate for {prefix!r} must be in [0, 1)")
        table[normalise_postal_code(str(prefix))] = rate
    return table


def put_country_rates(
    source: TableRateSource, calculator: TaxCalculator, country: str, body: dict[str, Any]
) -> Response:
    """PUT /admin/tax-rates/{country}: replace a country's table and drop its cached rates."""
    try:
        table = _parse_table(body.get("rates"))
    except ValueError as exc:
        return 400, {"error": str(exc)}
    country = country.upper()
    source.replace_country(country, table)
    dropped = calculator.rates_changed(country)
    return 200, {"country": country, "prefixes": len(table), "cache_entries_dropped": dropped}


def get_cache_stats(calculator: TaxCalculator) -> Response:
    """GET /admin/tax-rates/cache: hit ratio and size of the rate cache."""
    stats = calculator.cache_stats()
    return 200, {
        "hits": stats.hits,
        "misses": stats.misses,
        "evictions": stats.evictions,
        "size": stats.size,
        "hit_ratio": round(stats.hit_ratio, 4),
    }
