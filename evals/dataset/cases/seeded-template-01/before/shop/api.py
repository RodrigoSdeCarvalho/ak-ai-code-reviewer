"""HTTP handlers for the orders service. Handlers take parsed query parameters and return (status, body)."""

from __future__ import annotations

from typing import Any

from shop.orders import OrderNotFound, OrderRepository

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
