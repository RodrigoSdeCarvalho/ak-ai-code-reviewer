from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from podsync.models import Episode, Show, parse_episode, parse_show


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"{status}: {message}")
        self.status = status


class RateLimited(ApiError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(429, f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


class Transport(Protocol):
    def get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]: ...


class HostingClient:
    def __init__(self, transport: Transport, page_size: int = 50) -> None:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        self._transport = transport
        self._page_size = page_size

    def show(self, show_id: str) -> Show:
        return parse_show(self._transport.get(f"/v2/shows/{show_id}", {}))

    def latest_episodes(self, show_id: str, limit: int = 20) -> list[Episode]:
        payload = self._transport.get(
            f"/v2/shows/{show_id}/episodes",
            {"limit": str(min(limit, 100)), "order": "newest"},
        )
        return [parse_episode(show_id, item) for item in payload["items"]]
