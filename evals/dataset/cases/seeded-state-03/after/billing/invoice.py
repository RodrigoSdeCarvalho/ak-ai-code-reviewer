"""Invoice assembly for checkout and the monthly billing run."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from billing.tax import TaxCalculator, TaxLine


@dataclass(frozen=True)
class Address:
    country: str
    postal_code: str


@dataclass(frozen=True)
class LineItem:
    description: str
    unit_price: Decimal
    quantity: int

    @property
    def net(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Invoice:
    customer_id: str
    address: Address
    items: list[LineItem]
    tax_lines: list[TaxLine] = field(default_factory=list)

    @property
    def net_total(self) -> Decimal:
        return sum((item.net for item in self.items), Decimal("0"))

    @property
    def tax_total(self) -> Decimal:
        return sum((line.tax for line in self.tax_lines), Decimal("0"))

    @property
    def gross_total(self) -> Decimal:
        return self.net_total + self.tax_total


class InvoiceBuilder:
    """Long-lived: one builder serves every checkout and billing run in the process."""

    def __init__(self, calculator: TaxCalculator) -> None:
        self._calculator = calculator

    def build(self, customer_id: str, address: Address, items: list[LineItem]) -> Invoice:
        if not items:
            raise ValueError("an invoice needs at least one item")
        tax_lines = self._calculator.tax_lines(
            address.country,
            address.postal_code,
            [(item.description, item.net) for item in items],
        )
        return Invoice(customer_id, address, list(items), tax_lines)
