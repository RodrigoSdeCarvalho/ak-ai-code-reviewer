import sqlite3
from datetime import datetime, timedelta

import pytest
from podsync.client import HostingClient, RateLimited
from podsync.store import CatalogueStore
from podsync.sync import import_back_catalogue, import_shows

NOW = datetime(2026, 9, 1, 12, 0)
BASE = datetime(2020, 1, 6, 5, 0)


class FakeHosting:
    def __init__(self, catalogues: dict[str, int], limit_at: int | None = None) -> None:
        self.catalogues = catalogues
        self.limit_at = limit_at
        self.requests = 0

    def _item(self, show_id: str, i: int) -> dict:
        return {
            "id": f"{show_id}-ep{i:04d}",
            "title": f" Episode {i} ",
            "published_at": (BASE + timedelta(days=7 * i)).isoformat(),
            "audio": {"url": f"https://cdn.example.net/{show_id}/{i}.mp3", "duration": 1800 + i},
            "explicit": i % 5 == 0,
        }

    def get(self, path: str, params: dict) -> dict:
        self.requests += 1
        if self.limit_at is not None and self.requests == self.limit_at:
            raise RateLimited(60)
        show_id = path.split("/")[3]
        total = self.catalogues[show_id]
        assert params["order"] == "oldest"
        size = int(params["limit"])
        offset = int(params.get("cursor", "c0")[1:])
        items = [self._item(show_id, i) for i in range(offset, min(offset + size, total))]
        nxt = offset + size
        return {"items": items, "next_cursor": f"c{nxt}" if nxt < total else None}


def _store() -> CatalogueStore:
    return CatalogueStore(sqlite3.connect(":memory:"))


def test_full_import_requests_each_page_once():
    hosting = FakeHosting({"pod-1": 300})
    store = _store()
    result = import_back_catalogue(HostingClient(hosting, page_size=10), store, "pod-1", now=NOW)
    assert result.complete
    assert result.pages == 30
    assert result.inserted == 300
    assert hosting.requests <= 31


def test_resumed_import_does_not_rewalk_for_every_page():
    hosting = FakeHosting({"pod-1": 200})
    store = _store()
    client = HostingClient(hosting, page_size=10)
    first = import_back_catalogue(client, store, "pod-1", now=NOW, max_pages=5)
    assert (first.pages, first.complete) == (5, False)
    assert store.checkpoint("pod-1") == 5
    hosting.requests = 0
    second = import_back_catalogue(client, store, "pod-1", now=NOW)
    assert second.complete and second.pages == 15
    assert hosting.requests <= 5 + 15 + 1


def test_rate_limit_stops_the_run_and_resume_finishes_the_catalogue():
    hosting = FakeHosting({"pod-1": 45, "pod-2": 7}, limit_at=4)
    store = _store()
    client = HostingClient(hosting, page_size=10)
    run = import_shows(client, store, ["pod-1", "pod-2"], now=NOW)
    assert run.retry_after == 60
    assert run.pending == ["pod-1", "pod-2"]
    assert run.results["pod-2"].pages == 0
    assert store.checkpoint("pod-2") == 0

    hosting.limit_at = None
    run = import_shows(client, store, ["pod-1", "pod-2"], now=NOW)
    assert run.retry_after is None and run.pending == []
    assert store.count("pod-1") == 45
    assert store.count("pod-2") == 7
    assert store.episode_ids("pod-1")[:2] == ["pod-1-ep0000", "pod-1-ep0001"]
    assert store.imported_at("pod-1") == NOW

    hosting.requests = 0
    again = import_back_catalogue(client, store, "pod-1", now=NOW)
    assert again.complete and again.pages == 0 and hosting.requests == 0


def test_checkpoint_past_the_end_completes_without_episodes():
    hosting = FakeHosting({"pod-1": 20})
    store = _store()
    store.save_checkpoint("pod-1", 4)
    result = import_back_catalogue(HostingClient(hosting, page_size=10), store, "pod-1", now=NOW)
    assert result.complete and result.inserted == 0
    assert store.imported_at("pod-1") == NOW


def test_page_size_is_validated():
    with pytest.raises(ValueError):
        HostingClient(FakeHosting({}), page_size=0)
