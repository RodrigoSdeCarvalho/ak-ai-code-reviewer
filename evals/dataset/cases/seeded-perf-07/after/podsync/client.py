from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
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


@dataclass(frozen=True)
class EpisodePage:
    number: int
    episodes: list[Episode]
    has_more: bool


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

    def _oldest_first(self, show_id: str, cursor: str | None) -> dict[str, Any]:
        params = {"limit": str(self._page_size), "order": "oldest"}
        if cursor is not None:
            params["cursor"] = cursor
        return self._transport.get(f"/v2/shows/{show_id}/episodes", params)

    def episode_page(self, show_id: str, number: int) -> EpisodePage:
        """Return page `number` (0-based) of the show's episodes, oldest first.

        Cursors issued by the hosting API expire after a few minutes, so callers that need
        to resume later address pages by number.
        """
        cursor: str | None = None
        for _ in range(number):
            cursor = self._oldest_first(show_id, cursor).get("next_cursor")
            if cursor is None:
                return EpisodePage(number, [], has_more=False)
        payload = self._oldest_first(show_id, cursor)
        episodes = [parse_episode(show_id, item) for item in payload["items"]]
        return EpisodePage(number, episodes, has_more=payload.get("next_cursor") is not None)
