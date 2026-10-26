import random
from datetime import datetime, timedelta

import pytest
from workspace.invites import InviteNotUsable, InviteService
from workspace.members import Directory, Forbidden, Role

T0 = datetime(2026, 3, 2, 10, 0)


def _setup() -> tuple[Directory, InviteService]:
    directory = Directory()
    directory.add(1, 100, "owner@example.com", Role.OWNER, T0)
    directory.add(1, 101, "dev@example.com", Role.MEMBER, T0)
    return directory, InviteService(directory)


def test_link_lets_a_new_user_join_with_its_role():
    directory, invites = _setup()
    link = invites.create_link(1, 100, Role.MEMBER, T0, max_uses=2)
    assert link.url("https://app.example.com/") == f"https://app.example.com/join/{link.code}"
    member = invites.accept(link.code, 200, "New@Example.com", T0 + timedelta(hours=1))
    assert member.role is Role.MEMBER and member.invite_code == link.code
    assert directory.is_member(1, 200)
    invites.accept(link.code, 201, "other@example.com", T0 + timedelta(hours=2))
    with pytest.raises(InviteNotUsable):
        invites.accept(link.code, 202, "third@example.com", T0 + timedelta(hours=3))


def test_plain_member_cannot_create_links():
    _, invites = _setup()
    with pytest.raises(Forbidden):
        invites.create_link(1, 101, Role.MEMBER, T0)


def test_revoked_link_is_refused():
    _, invites = _setup()
    link = invites.create_link(1, 100, Role.GUEST, T0)
    invites.revoke(link.code, 100)
    with pytest.raises(InviteNotUsable):
        invites.accept(link.code, 300, "guest@example.com", T0)


def test_expired_link_cannot_be_used_to_join():
    directory, invites = _setup()
    link = invites.create_link(1, 100, Role.MEMBER, T0, ttl=timedelta(days=7))
    with pytest.raises(InviteNotUsable):
        invites.accept(link.code, 400, "late@example.com", T0 + timedelta(days=8))
    assert not directory.is_member(1, 400)


def test_link_codes_do_not_depend_on_the_shared_random_state():
    _, invites = _setup()
    _, restarted = _setup()
    random.seed(2026)
    first = invites.create_link(1, 100, Role.MEMBER, T0)
    random.seed(2026)
    second = restarted.create_link(1, 100, Role.MEMBER, T0)
    assert first.code != second.code
    assert len(first.code) == 22 and first.code.isalnum()
