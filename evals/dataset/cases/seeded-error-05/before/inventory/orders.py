"""POST /orders handler: validate the order lines and reserve their stock."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inventory.warehouse import UnknownSku, Warehouse

Response = tuple[int, dict[str, Any]]

MAX_LINES = 50


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int


def parse_lines(payload: dict[str, Any]) -> list[OrderLine]:
    """Validate `payload["lines"]`; each SKU may appear only once."""
    raw = payload.get("lines")
    if not isinstance(raw, list) or not raw:
        raise ValueError("lines must be a non-empty list")
    if len(raw) > MAX_LINES:
        raise ValueError(f"at most {MAX_LINES} lines per order")
    lines: list[OrderLine] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("each line must be an object")
        sku, quantity = item.get("sku"), item.get("quantity")
        if not isinstance(sku, str) or not sku:
            raise ValueError("each line needs a sku")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError(f"{sku}: quantity must be a positive integer")
        if sku in seen:
            raise ValueError(f"{sku}: listed more than once")
        seen.add(sku)
        lines.append(OrderLine(sku, quantity))
    return lines


def place_order(warehouse: Warehouse, payload: dict[str, Any]) -> Response:
    try:
        lines = parse_lines(payload)
    except ValueError as exc:
        return 400, {"error": str(exc)}
    try:
        for line in lines:
            if warehouse.available(line.sku) < line.quantity:
                return 409, {"error": "insufficient stock", "sku": line.sku}
    except UnknownSku as exc:
        return 404, {"error": f"unknown sku {exc.args[0]}"}
    for line in lines:
        warehouse.reserve(line.sku, line.quantity)
    return 201, {"reserved": {line.sku: line.quantity for line in lines}}
