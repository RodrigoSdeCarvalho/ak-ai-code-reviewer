from datetime import datetime, timedelta

import pytest

from audit.handlers import MAX_PAGE_SIZE, decode_cursor, encode_cursor, get_event, list_events
from audit.store import AuditStore

T0 = datetime(2026, 4, 1, 9, 0)


def _store(n: int) -> AuditStore:
    store = AuditStore()
    for i in range(n):
        actor = "alice" if i % 3 else "bob"
        store.append(actor, "role.grant" if i % 2 else "user.login", f"user-{i}", T0 + timedelta(minutes=i))
    return store


def _all_pages(store, **params):
    ids, pages, cursor = [], 0, None
    while True:
        query = dict(params)
        if cursor is not None:
            query["cursor"] = cursor
        response = list_events(store, query)
        assert response.status == 200
        pages += 1
        ids += [event["id"] for event in response.body["events"]]
        cursor = response.body["next_cursor"]
        if cursor is None:
            return ids, pages


@pytest.mark.parametrize(("total", "limit", "pages"), [(25, 10, 3), (30, 10, 3), (9, 10, 1), (10, 10, 1), (1, 1, 1)])
def test_paging_visits_every_event_once(total, limit, pages):
    ids, page_count = _all_pages(_store(total), limit=str(limit))
    assert ids == list(range(total, 0, -1))
    assert page_count == pages


def test_exact_multiple_has_no_empty_trailing_page():
    first = list_events(_store(20), {"limit": "10"})
    second = list_events(_store(20), {"limit": "10", "cursor": first.body["next_cursor"]})
    assert len(second.body["events"]) == 10
    assert second.body["next_cursor"] is None


def test_filters_apply_across_pages():
    store = _store(40)
    ids, _ = _all_pages(store, actor="bob", limit="4")
    assert ids == [e.id for e in store.query(actor="bob")]
    assert len(ids) == 14


def test_empty_store():
    response = list_events(AuditStore(), {})
    assert response.body == {"events": [], "next_cursor": None}


def test_default_and_capped_page_size():
    store = _store(MAX_PAGE_SIZE + 60)
    assert len(list_events(store, {}).body["events"]) == 50
    assert len(list_events(store, {"limit": "100000"}).body["events"]) == MAX_PAGE_SIZE


@pytest.mark.parametrize(
    "params",
    [{"limit": "0"}, {"limit": "-5"}, {"limit": "ten"}, {"cursor": "!!!"}, {"cursor": "djE6MA=="}, {"cursor": "abc"}],
)
def test_bad_parameters_are_400(params):
    response = list_events(_store(5), params)
    assert response.status == 400
    assert "error" in response.body


def test_cursor_round_trip_and_exclusive_bound():
    store = _store(10)
    assert decode_cursor(encode_cursor(7)) == 7
    response = list_events(store, {"cursor": encode_cursor(7)})
    assert [e["id"] for e in response.body["events"]] == [6, 5, 4, 3, 2, 1]
    assert list_events(store, {"cursor": encode_cursor(1)}).body["events"] == []
    assert len(list_events(store, {"cursor": encode_cursor(999)}).body["events"]) == 10


def test_store_query_limits():
    store = _store(6)
    assert store.query(limit=0) == []
    assert [e.id for e in store.query(limit=2)] == [6, 5]
    assert [e.id for e in store.query(before_id=4, limit=10)] == [3, 2, 1]


def test_get_event_unchanged():
    store = _store(3)
    assert get_event(store, "2").body["id"] == 2
    assert get_event(store, "4").status == 404
    assert get_event(store, "x").status == 404
