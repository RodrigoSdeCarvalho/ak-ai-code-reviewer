from datetime import datetime, timedelta

import pytest

from auth.sessions import InvalidCredentials, InvalidSession, SessionManager, token_hash
from auth.store import FileSessionStore, MemorySessionStore, StoreError
from auth.users import UserDirectory

T0 = datetime(2026, 6, 1, 9, 0)
ANA = ("ana@example.com", "correct horse")
BO = ("bo@example.com", "battery staple")


def _users() -> UserDirectory:
    users = UserDirectory(iterations=1000)
    users.create(*ANA)
    users.create(*BO)
    return users


class FlakyStore(MemorySessionStore):
    """A memory store whose delete fails for selected sessions."""

    def __init__(self) -> None:
        super().__init__()
        self.failing: set[str] = set()

    def delete(self, access_hash: str) -> None:
        if access_hash in self.failing:
            raise StoreError("backend timed out")
        super().delete(access_hash)


def test_login_authenticate_and_refresh_rotation():
    manager = SessionManager(_users(), MemorySessionStore())
    with pytest.raises(InvalidCredentials):
        manager.login(ANA[0], "wrong", T0)
    first = manager.login(*ANA, T0)
    assert manager.authenticate(first.access_token, T0 + timedelta(minutes=10)).email == ANA[0]
    with pytest.raises(InvalidSession):
        manager.authenticate(first.access_token, T0 + timedelta(minutes=30))
    second = manager.refresh(first.refresh_token, T0 + timedelta(minutes=20))
    assert manager.authenticate(second.access_token, T0 + timedelta(minutes=21)).id == 1
    with pytest.raises(InvalidSession):
        manager.authenticate(first.access_token, T0 + timedelta(minutes=21))
    with pytest.raises(InvalidSession):
        manager.refresh(first.refresh_token, T0 + timedelta(minutes=22))


def test_file_store_persists_hashed_sessions(tmp_path):
    path = tmp_path / "sessions.json"
    users = _users()
    issued = SessionManager(users, FileSessionStore(path)).login(*ANA, T0)
    reopened = SessionManager(users, FileSessionStore(path))
    assert reopened.authenticate(issued.access_token, T0).id == 1
    content = path.read_text(encoding="utf-8")
    assert issued.access_token not in content and issued.refresh_token not in content
    assert FileSessionStore(tmp_path / "missing.json").all() == []


def test_corrupt_session_file_is_reported_not_overwritten(tmp_path):
    path = tmp_path / "sessions.json"
    manager = SessionManager(_users(), FileSessionStore(path))
    manager.login(*ANA, T0)
    damaged = path.read_bytes()[:-7]
    path.write_bytes(damaged)
    with pytest.raises(StoreError):
        manager.login(*BO, T0)
    assert path.read_bytes() == damaged


def test_password_change_reports_a_session_it_could_not_end():
    store = FlakyStore()
    manager = SessionManager(_users(), store)
    manager.login(*ANA, T0)
    phone = manager.login(*ANA, T0)
    store.failing.add(token_hash(phone.access_token))
    with pytest.raises(StoreError):
        manager.change_password(1, "new passphrase")


def test_sign_out_everywhere_and_purge():
    manager = SessionManager(_users(), MemorySessionStore())
    laptop = manager.login(*ANA, T0)
    manager.login(*ANA, T0)
    other = manager.login(*BO, T0)
    assert manager.sign_out_everywhere(1) == 2
    with pytest.raises(InvalidSession):
        manager.authenticate(laptop.access_token, T0)
    assert manager.authenticate(other.access_token, T0).id == 2
    assert manager.purge_expired(T0 + timedelta(days=13)) == 0
    assert manager.purge_expired(T0 + timedelta(days=14)) == 1
