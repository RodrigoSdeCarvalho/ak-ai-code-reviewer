"""Request handlers for the catalogue API."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from catalog.models import Product
from catalog.service import SearchService

Response = tuple[int, dict[str, Any]]

SORTS: dict[str, Callable[[Product], Any]] = {
    "price": lambda p: (p.price, p.sku),
    "-price": lambda p: (-p.price, p.sku),
    "rating": lambda p: (-p.rating, p.sku),
}
MAX_LIMIT = 100


def search_products(service: SearchService, params: Mapping[str, str]) -> Response:
    """GET /products/search?q=...&tags=a,b&sort=relevance|price|-price|rating&limit=N"""
    query = params.get("q", "").strip()
    if not query:
        return 400, {"error": "q is required"}
    sort = params.get("sort", "relevance")
    if sort != "relevance" and sort not in SORTS:
        return 400, {"error": f"unknown sort {sort!r}"}
    try:
        limit = int(params.get("limit", "20"))
    except ValueError:
        return 400, {"error": "limit must be an integer"}
    if not 1 <= limit <= MAX_LIMIT:
        return 400, {"error": f"limit must be between 1 and {MAX_LIMIT}"}
    tags = [t for t in params.get("tags", "").split(",") if t]

    hits = service.find(query, tags)
    if sort != "relevance":
        hits.sort(key=SORTS[sort])
    return 200, {
        "query": query,
        "count": len(hits),
        "results": [product.to_dict() for product in hits[:limit]],
    }
