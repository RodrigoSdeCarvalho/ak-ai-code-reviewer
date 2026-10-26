import json
import threading
from datetime import datetime, timedelta

import pytest

import sessions.store as store_mod
from sessions.store import FileSessionStore, SessionStore
from sessions.tokens import bearer_token, token_digest

NOW = datetime(2026, 10, 1, 9, 0)


def leftovers(directory):
    return sorted(p.name for p in directory.iterdir() if p.name.endswith(".tmp"))


def test_sessions_survive_a_restart(tmp_path):
    path = tmp_path / "sessions.json"
    first = FileSessionStore(path, ttl=timedelta(hours=1))
    alice = first.create("alice", NOW)
    bob = first.create("bob", NOW)
    assert first.revoke(bob)
    second = FileSessionStore(path, ttl=timedelta(hours=1))
    assert second.get(alice, NOW + timedelta(minutes=59)).user_id == "alice"
    assert second.get(bob, NOW) is None
    assert second.get(alice, NOW + timedelta(hours=1)) is None


def test_file_holds_digests_not_tokens(tmp_path):
    path = tmp_path / "sessions.json"
    token = FileSessionStore(path).create("alice", NOW)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert list(stored) == [token_digest(token)]
    assert token not in path.read_text(encoding="utf-8")


def test_failed_write_keeps_memory_and_file_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "sessions.json"
    sessions = FileSessionStore(path)
    kept = sessions.create("alice", NOW)
    before = path.read_text(encoding="utf-8")

    def broken_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(store_mod.os, "replace", broken_replace)
    with pytest.raises(OSError, match="disk full"):
        sessions.create("bob", NOW)
    with pytest.raises(OSError):
        sessions.revoke(kept)
    assert path.read_text(encoding="utf-8") == before
    assert sessions.get(kept, NOW).user_id == "alice"
    assert leftovers(tmp_path) == []


def test_interrupt_during_write_is_reraised_and_cleaned_up(tmp_path, monkeypatch):
    sessions = FileSessionStore(tmp_path / "sessions.json")

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(store_mod.json, "dump", interrupted)
    with pytest.raises(KeyboardInterrupt):
        sessions.create("alice", NOW)
    assert leftovers(tmp_path) == []
    assert not (tmp_path / "sessions.json").exists()


def test_revoke_user_and_purge(tmp_path):
    sessions = FileSessionStore(tmp_path / "s.json", ttl=timedelta(minutes=30))
    a1 = sessions.create("alice", NOW)
    sessions.create("alice", NOW + timedelta(minutes=20))
    b = sessions.create("bob", NOW + timedelta(minutes=20))
    assert sessions.purge_expired(NOW + timedelta(minutes=40)) == 1
    assert sessions.get(a1, NOW) is None
    assert sessions.revoke_user("alice") == 1
    assert sessions.revoke_user("alice") == 0
    assert FileSessionStore(tmp_path / "s.json").get(b, NOW + timedelta(minutes=21)).user_id == "bob"


def test_concurrent_creates_are_not_lost():
    sessions = SessionStore()
    barrier = threading.Barrier(8)
    tokens = []

    def worker(n):
        barrier.wait()
        for i in range(200):
            tokens.append(sessions.create(f"user-{n}-{i}", NOW))

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(sessions.get(t, NOW) is not None for t in tokens)
    assert len(tokens) == 1600


@pytest.mark.parametrize(
    ("header", "expected"),
    [("Bearer abc", "abc"), ("bearer  abc ", "abc"), ("Basic abc", None), ("Bearer", None), (None, None)],
)
def test_bearer_token(header, expected):
    assert bearer_token(header) == expected
