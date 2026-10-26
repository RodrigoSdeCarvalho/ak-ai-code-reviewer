from datetime import UTC, datetime, timedelta
from decimal import Decimal

from billing.admin import get_cache_stats, put_country_rates
from billing.invoice import Address, InvoiceBuilder, LineItem
from billing.tax import TableRateSource, TaxCalculator


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def _source() -> TableRateSource:
    return TableRateSource(
        {
            "US": {"9": Decimal("0.0725"), "10": Decimal("0.08875"), "*": Decimal("0.06")},
            "DE": {"*": Decimal("0.19")},
        }
    )


def test_cache_never_holds_more_than_cache_size_rates():
    calc = TaxCalculator(_source(), cache_size=3, clock=FakeClock())
    for zip_code in range(90001, 90021):
        calc.rate("us", str(zip_code))
    stats = calc.cache_stats()
    assert stats.size <= 3
    assert stats.evictions == 17


def test_least_recently_used_rate_is_evicted_first():
    source = _source()
    calc = TaxCalculator(source, cache_size=2, clock=FakeClock())
    calc.rate("US", "90001")
    calc.rate("US", "10001")
    calc.rate("US", "90001")
    calc.rate("DE", "10115")
    before = source.lookups
    calc.rate("US", "90001")
    assert source.lookups == before
    calc.rate("US", "10001")
    assert source.lookups == before + 1


def test_ttl_invalidation_and_admin_update():
    source, clock = _source(), FakeClock()
    calc = TaxCalculator(source, cache_ttl=timedelta(minutes=10), clock=clock)
    builder = InvoiceBuilder(calc)
    address = Address("US", "100 01")
    invoice = builder.build("c-1", address, [LineItem("Desk", Decimal("200.00"), 1)])
    assert invoice.tax_total == Decimal("17.75")
    status, body = put_country_rates(source, calc, "us", {"rates": {"10": "0.09", "*": "0.05"}})
    assert status == 200 and body["cache_entries_dropped"] == 1
    assert calc.rate("US", "10001") == Decimal("0.09")
    lookups = source.lookups
    clock.now += timedelta(minutes=11)
    assert calc.rate("US", "10001") == Decimal("0.09")
    assert source.lookups == lookups + 1
    assert put_country_rates(source, calc, "US", {"rates": {"10": "1.5"}})[0] == 400
    assert put_country_rates(source, calc, "US", {"rates": {"10": "NaN"}})[0] == 400
    assert get_cache_stats(calc)[1]["size"] == 1
