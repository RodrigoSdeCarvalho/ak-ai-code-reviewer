import json
from datetime import date, datetime, timedelta, timezone

from tracking.events import Event
from tracking.reports import account_timeline, daily_active_accounts, retention, session_stats, top_accounts
from tracking.store import EventStore

T0 = datetime(2026, 5, 4, 9, 0, tzinfo=timezone.utc)


def _store(tmp_path) -> EventStore:
    path = tmp_path / "events.jsonl"
    legacy = {"name": "signup", "at": T0.isoformat(), "user_id": "acc-1", "props": {}}
    path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
    store = EventStore(path)
    store.extend(
        [
            Event("signup", T0 + timedelta(hours=1), "acc-2", session_id="s-2"),
            Event("page_view", T0 + timedelta(days=1), None, {"path": "/pricing"}, "s-3"),
            Event("login", T0 + timedelta(days=1, minutes=5), "acc-1", session_id="s-3"),
            Event("purchase", T0 + timedelta(days=1, minutes=20), "acc-1", session_id="s-3"),
            Event("login", T0 + timedelta(days=2), "acc-2", session_id="s-4"),
        ]
    )
    return store


def test_account_timeline_includes_new_and_legacy_records(tmp_path):
    store = _store(tmp_path)
    assert account_timeline(store, "acc-1") == [
        (T0, "signup"),
        (T0 + timedelta(days=1, minutes=5), "login"),
        (T0 + timedelta(days=1, minutes=20), "purchase"),
    ]
    assert [name for _, name in account_timeline(store, "acc-2")] == ["signup", "login"]
    assert account_timeline(store, "acc-9") == []


def test_for_account_filters_records(tmp_path):
    store = _store(tmp_path)
    assert [record["name"] for record in store.for_account("acc-2")] == ["signup", "login"]


def test_aggregate_reports(tmp_path):
    store = _store(tmp_path)
    assert top_accounts(store.records()) == [("acc-1", 3), ("acc-2", 2)]
    assert daily_active_accounts(store.records()) == {date(2026, 5, 4): 2, date(2026, 5, 5): 1, date(2026, 5, 6): 1}
    assert retention(store.records(), date(2026, 5, 4), horizon=3) == [0.5, 0.5, 0.0]
    stats = session_stats(store.records())
    assert stats["s-3"].account_id == "acc-1"
    assert stats["s-3"].duration == timedelta(minutes=20)
    assert stats["s-3"].events == 3
    assert [event.account_id for event in store.events()] == ["acc-1", "acc-2", None, "acc-1", "acc-1", "acc-2"]
