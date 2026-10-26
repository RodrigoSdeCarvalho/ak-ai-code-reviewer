from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from podsync.client import HostingClient
from podsync.store import CatalogueStore


@dataclass
class RefreshResult:
    show_id: str
    inserted: int = 0
    updated: int = 0


def refresh_recent(
    client: HostingClient, store: CatalogueStore, show_id: str, limit: int = 20
) -> RefreshResult:
    result = RefreshResult(show_id)
    for episode in client.latest_episodes(show_id, limit):
        if store.upsert_episode(episode):
            result.inserted += 1
        else:
            result.updated += 1
    return result


def refresh_all(
    client: HostingClient, store: CatalogueStore, show_ids: Iterable[str], limit: int = 20
) -> dict[str, RefreshResult]:
    return {show_id: refresh_recent(client, store, show_id, limit) for show_id in show_ids}


def stale_shows(
    store: CatalogueStore, show_ids: Iterable[str], now: datetime, max_age: timedelta
) -> list[str]:
    stale = []
    for show_id in show_ids:
        latest = store.latest_published(show_id)
        if latest is None or now - latest > max_age:
            stale.append(show_id)
    return stale
