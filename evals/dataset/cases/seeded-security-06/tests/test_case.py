from boxoffice.handlers import BoxOfficeApi
from boxoffice.models import Event, Request, Role, User
from boxoffice.store import TicketStore

ADA = User(1, "Ada", Role.ATTENDEE)
BEN = User(2, "Ben", Role.ATTENDEE)
SAM = User(3, "Sam", Role.STAFF)
ROOT = User(4, "Root", Role.ADMIN)


def _api() -> tuple[BoxOfficeApi, TicketStore]:
    store = TicketStore()
    store.add_event(Event(10, "Jazz Night", capacity=20, price_cents=3500))
    return BoxOfficeApi(store), store


def test_staff_can_issue_comps_that_cost_nothing():
    api, store = _api()
    resp = api.handle(
        "tickets.comp",
        Request(SAM, {"event_id": "10", "holder_id": "2", "quantity": "2", "note": "press"}),
    )
    assert resp.status == 201
    tickets = resp.body["tickets"]
    assert [t["price_paid_cents"] for t in tickets] == [0, 0]
    assert all(t["comp"] for t in tickets)
    assert store.remaining(10) == 18


def test_attendee_list_counts_valid_tickets_for_staff_only():
    api, _ = _api()
    api.handle("tickets.buy", Request(ADA, {"event_id": "10", "quantity": "3"}))
    api.handle("tickets.buy", Request(BEN, {"event_id": "10", "quantity": "1"}))
    assert api.handle("event.attendees", Request(ADA, {"event_id": "10"})).status == 403
    resp = api.handle("event.attendees", Request(ROOT, {"event_id": "10"}))
    assert resp.status == 200
    assert resp.body["total"] == 4
    assert resp.body["attendees"][0] == {"holder_id": 1, "tickets": 3}


def test_attendee_cannot_issue_comps():
    api, store = _api()
    resp = api.handle(
        "tickets.comp",
        Request(ADA, {"event_id": "10", "holder_id": "1", "quantity": "4"}),
    )
    assert resp.status == 403
    assert store.remaining(10) == 20


def test_signed_out_comp_request_is_unauthorized():
    api, _ = _api()
    resp = api.handle("tickets.comp", Request(None, {"event_id": "10", "holder_id": "1"}))
    assert resp.status == 401
