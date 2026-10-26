from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from podsync.client import HostingClient, RateLimited
from podsync.store import CatalogueStore


@dataclass
class RefreshResult:
    show_id: str
    inserted: int = 0
    updated: int = 0


@dataclass
class ImportResult:
    show_id: str
    pages: int = 0
    inserted: int = 0
    updated: int = 0
    complete: bool = False
    retry_after: int | None = None


@dataclass
class ImportRun:
    results: dict[str, ImportResult] = field(default_factory=dict)
    retry_after: int | None = None

    @property
    def pending(self) -> list[str]:
        return [show_id for show_id, result in self.results.items() if not result.complete]


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


def import_back_catalogue(
    client: HostingClient,
    store: CatalogueStore,
    show_id: str,
    *,
    now: datetime,
    max_pages: int | None = None,
) -> ImportResult:
    result = ImportResult(show_id)
    if store.imported_at(show_id) is not None:
        result.complete = True
        return result
    number = store.checkpoint(show_id)
    while max_pages is None or result.pages < max_pages:
        try:
            page = client.episode_page(show_id, number)
        except RateLimited as exc:
            result.retry_after = exc.retry_after
            return result
        for episode in page.episodes:
            if store.upsert_episode(episode):
                result.inserted += 1
            else:
                result.updated += 1
        result.pages += 1
        number += 1
        store.save_checkpoint(show_id, number)
        if not page.has_more:
            store.mark_imported(show_id, now)
            result.complete = True
            break
    return result


def import_shows(
    client: HostingClient,
    store: CatalogueStore,
    show_ids: Iterable[str],
    *,
    now: datetime,
    max_pages_per_show: int | None = None,
) -> ImportRun:
    run = ImportRun()
    for show_id in show_ids:
        if run.retry_after is not None:
            run.results[show_id] = ImportResult(show_id)
            continue
        result = import_back_catalogue(client, store, show_id, now=now, max_pages=max_pages_per_show)
        run.results[show_id] = result
        run.retry_after = result.retry_after
    return run
