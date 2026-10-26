"""HTTP handlers for the orders service. Handlers take parsed query parameters and return (status, body)."""

from __future__ import annotations

from typing import Any

from shop.orders import OrderNotFound, OrderRepository
from shop.pagination import DEFAULT_PER_PAGE, paginate

Response = tuple[int, dict[str, Any]]


def _int_param(params: dict[str, str], name: str, default: int | None = None) -> int:
    raw = params.get(name)
    if raw is None:
        if default is None:
            raise ValueError(f"missing parameter {name!r}")
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"parameter {name!r} must be an integer") from None


def get_order(repo: OrderRepository, params: dict[str, str]) -> Response:
    """GET /orders/{id}"""
    try:
        order_id = _int_param(params, "id")
    except ValueError as exc:
        return 400, {"error": str(exc)}
    try:
        order = repo.get(order_id)
    except OrderNotFound:
        return 404, {"error": f"order {order_id} not found"}
    return 200, order.to_dict()


def list_orders(repo: OrderRepository, params: dict[str, str]) -> Response:
    """GET /customers/{customer_id}/orders?page=N&per_page=M, newest first."""
    try:
        customer_id = _int_param(params, "customer_id")
        page = _int_param(params, "page", default=1)
        per_page = _int_param(params, "per_page", default=DEFAULT_PER_PAGE)
        result = paginate(repo.for_customer(customer_id), page, per_page)
    except ValueError as exc:
        return 400, {"error": str(exc)}
    return 200, {
        "orders": [order.to_dict() for order in result.items],
        "page": result.page,
        "per_page": result.per_page,
        "total": result.total,
        "total_pages": result.total_pages,
        "has_next": result.has_next,
    }
