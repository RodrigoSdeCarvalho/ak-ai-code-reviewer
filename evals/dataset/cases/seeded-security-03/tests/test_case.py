import re
import random
from datetime import date, datetime, timedelta

import pytest
from allotment.magic_links import LinkRejected, MagicLinkService
from allotment.mailer import Outbox
from allotment.members import Member, MemberDirectory
from allotment.sessions import SessionStore

T0 = datetime(2026, 4, 2, 8, 0)


def _setup() -> tuple[MagicLinkService, SessionStore, Outbox]:
    members = MemberDirectory(
        [
            Member(1, "Priya", "priya@example.org", date(2019, 3, 1), plot="B12"),
            Member(2, "Tom", "tom@example.org", date(2024, 6, 9), active=False),
        ]
    )
    sessions = SessionStore()
    outbox = Outbox()
    return MagicLinkService(members, sessions, outbox, "https://members.example.org/"), sessions, outbox


def _token_from(outbox: Outbox) -> str:
    match = re.search(r"/login/(\S+)", outbox.messages[-1].body)
    assert match is not None
    return match.group(1)


def test_link_token_does_not_depend_on_the_random_module_state():
    service, _, outbox = _setup()
    random.seed(1234)
    service.request_link("Priya@Example.org ", T0)
    first = _token_from(outbox)
    random.seed(1234)
    service.request_link("priya@example.org", T0)
    second = _token_from(outbox)
    assert first != second
    assert len(first) >= 32


def test_expired_link_is_refused():
    service, _, outbox = _setup()
    service.request_link("priya@example.org", T0)
    token = _token_from(outbox)
    with pytest.raises(LinkRejected):
        service.redeem(token, T0 + timedelta(minutes=16))


def test_link_signs_in_once():
    service, sessions, outbox = _setup()
    service.request_link("priya@example.org", T0)
    token = _token_from(outbox)
    session = service.redeem(token, T0 + timedelta(minutes=14))
    assert session.member_id == 1 and session.method == "magic_link"
    assert sessions.lookup(session.id, T0 + timedelta(days=1)) == session
    with pytest.raises(LinkRejected):
        service.redeem(token, T0 + timedelta(minutes=14))


def test_unknown_or_inactive_addresses_get_no_mail_and_pending_is_capped():
    service, _, outbox = _setup()
    service.request_link("nobody@example.org", T0)
    service.request_link("tom@example.org", T0)
    assert outbox.messages == []
    for i in range(5):
        service.request_link("priya@example.org", T0 + timedelta(minutes=i))
    assert service.pending_count(1) == 3
    assert service.purge_expired(T0 + timedelta(minutes=18)) == 2
    assert service.pending_count(1) == 1
