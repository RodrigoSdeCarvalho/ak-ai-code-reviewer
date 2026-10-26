"""Page-number pagination for list endpoints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


def paginate(items: Sequence[T], page: int, per_page: int = DEFAULT_PER_PAGE) -> Page[T]:
    """Return page `page` (1-based) of `items`, `per_page` items per page.

    Raises ValueError for a page below 1 or a page size outside 1..MAX_PER_PAGE. A page past the end
    is returned empty, so clients can simply stop when `has_next` is false.
    """
    if page < 1:
        raise ValueError("page must be >= 1")
    if not 1 <= per_page <= MAX_PER_PAGE:
        raise ValueError(f"per_page must be between 1 and {MAX_PER_PAGE}")
    total = len(items)
    total_pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    return Page(
        items=list(items[start : start + per_page]),
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
    )
