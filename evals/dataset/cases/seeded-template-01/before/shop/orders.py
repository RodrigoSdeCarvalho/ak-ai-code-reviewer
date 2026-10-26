"""Order records and the in-memory repository used by the HTTP handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


class OrderNotFound(KeyError):
    """Raised when an order id is unknown."""


@dataclass(frozen=True)
class Order:
    id: int
    customer_id: int
    total: Decimal
    status: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "total": str(self.total),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OrderRepository:
    _orders: dict[int, Order] = field(default_factory=dict)

    def add(self, order: Order) -> None:
        if order.id in self._orders:
            raise ValueError(f"order {order.id} already exists")
        self._orders[order.id] = order

    def get(self, order_id: int) -> Order:
        try:
            return self._orders[order_id]
        except KeyError:
            raise OrderNotFound(order_id) from None

    def for_customer(self, customer_id: int) -> list[Order]:
        """Orders of one customer, newest first."""
        orders = [o for o in self._orders.values() if o.customer_id == customer_id]
        return sorted(orders, key=lambda o: (o.created_at, o.id), reverse=True)
