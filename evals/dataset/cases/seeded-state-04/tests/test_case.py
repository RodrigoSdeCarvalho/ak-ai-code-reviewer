import itertools
import threading
from datetime import UTC, datetime, timedelta

from auth.handlers import AccountDirectory, login, logout, whoami
from auth.sessions import SessionStore

NOW = datetime(2026, 5, 4, 9, 30, tzinfo=UTC)


class RendezvousTokens:
    """Token factory whose first two calls wait (briefly) for each other."""

    def __init__(self) -> None:
        self._barrier = threading.Barrier(2)
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def __call__(self) -> str:
        try:
            self._barrier.wait(timeout=0.3)
        except threading.BrokenBarrierError:
            pass
        with self._lock:
            return f"tok-{next(self._counter)}"


def _login_in_parallel(store: SessionStore, user_id: str) -> list[str]:
    tokens: list[str] = []
    guard = threading.Lock()

    def worker() -> None:
        token = store.login(user_id).token
        with guard:
            tokens.append(token)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return tokens


def test_parallel_logins_share_one_live_session():
    store = SessionStore(clock=lambda: NOW, token_factory=RendezvousTokens())
    tokens = _login_in_parallel(store, "ada")
    assert len(tokens) == 2
    assert tokens[0] == tokens[1]
    assert all(store.validate(token) is not None for token in tokens)


def test_login_reuses_live_session_and_replaces_expired_one():
    now = [NOW]
    counter = itertools.count(1)
    store = SessionStore(
        ttl=timedelta(hours=1), clock=lambda: now[0], token_factory=lambda: f"t{next(counter)}"
    )
    first = store.login("ada")
    assert store.login("ada").token == first.token
    now[0] = NOW + timedelta(hours=2)
    second = store.login("ada")
    assert second.token != first.token
    assert store.validate(second.token) is not None
    assert store.validate(first.token) is None


def test_reused_session_gets_a_fresh_expiry():
    now = [NOW]
    store = SessionStore(ttl=timedelta(hours=1), clock=lambda: now[0], token_factory=lambda: "t1")
    first = store.login("ada")
    now[0] = NOW + timedelta(minutes=50)
    again = store.login("ada")
    assert again.token == first.token
    assert again.expires_at == now[0] + timedelta(hours=1)
    now[0] = NOW + timedelta(minutes=90)
    assert store.validate(first.token) == again


def test_handlers_sign_in_twice_then_out():
    directory = AccountDirectory()
    directory.add("ada", "correct horse", salt=b"0123456789abcdef")
    store = SessionStore(clock=lambda: NOW)
    status, first = login(directory, store, {"user_id": "ada", "password": "correct horse"})
    assert status == 200
    _, second = login(directory, store, {"user_id": "ada", "password": "correct horse"})
    assert second["token"] == first["token"]
    headers = {"authorization": f"Bearer {first['token']}"}
    assert whoami(store, headers) == (200, {"user_id": "ada", "expires_at": second["expires_at"]})
    assert login(directory, store, {"user_id": "ada", "password": "nope"})[0] == 401
    assert login(directory, store, {"user_id": "bob", "password": "x"})[0] == 401
    assert logout(store, headers)[0] == 204
    assert whoami(store, headers)[0] == 401
