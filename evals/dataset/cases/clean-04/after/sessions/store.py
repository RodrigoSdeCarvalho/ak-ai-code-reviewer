"""Server-side session storage keyed by token digest."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta
from pathlib import Path

from sessions.tokens import Session, decode_session, encode_session, new_token, token_digest

DEFAULT_TTL = timedelta(hours=12)


class SessionStore:
    """In-memory sessions for a single application process."""

    def __init__(self, ttl: timedelta = DEFAULT_TTL, sessions: Mapping[str, Session] | None = None) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        self._ttl = ttl
        self._sessions: dict[str, Session] = dict(sessions or {})
        self._write_lock = threading.Lock()

    def _commit(self, sessions: dict[str, Session]) -> None:
        """Replace the current sessions with `sessions`; called with the write lock held."""
        self._sessions = sessions

    def create(self, user_id: str, now: datetime) -> str:
        """Start a session for `user_id` and return the bearer token."""
        token = new_token()
        session = Session(user_id, created_at=now, expires_at=now + self._ttl)
        with self._write_lock:
            self._commit({**self._sessions, token_digest(token): session})
        return token

    def get(self, token: str, now: datetime) -> Session | None:
        """The live session for `token`, or None if unknown or expired."""
        session = self._sessions.get(token_digest(token))
        if session is None or session.is_expired(now):
            return None
        return session

    def revoke(self, token: str) -> bool:
        """End one session; False if it did not exist."""
        digest = token_digest(token)
        with self._write_lock:
            if digest not in self._sessions:
                return False
            self._commit({d: s for d, s in self._sessions.items() if d != digest})
        return True

    def revoke_user(self, user_id: str) -> int:
        """End every session of `user_id` (password change, account lock); returns how many."""
        with self._write_lock:
            kept = {d: s for d, s in self._sessions.items() if s.user_id != user_id}
            removed = len(self._sessions) - len(kept)
            if removed:
                self._commit(kept)
        return removed

    def purge_expired(self, now: datetime) -> int:
        """Drop expired sessions; returns how many were dropped."""
        with self._write_lock:
            kept = {d: s for d, s in self._sessions.items() if not s.is_expired(now)}
            removed = len(self._sessions) - len(kept)
            if removed:
                self._commit(kept)
        return removed


class FileSessionStore(SessionStore):
    """Sessions persisted to a JSON file so that a restart does not log everyone out.

    Each change is written to a temporary file in the same directory and renamed over the
    previous file; the in-memory state changes only after the rename succeeded. Like
    SessionStore, it serves one application process; the file is not shared between workers.
    """

    def __init__(self, path: Path, ttl: timedelta = DEFAULT_TTL) -> None:
        self._path = path
        super().__init__(ttl, self._load())

    def _load(self) -> dict[str, Session]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        return {digest: decode_session(data) for digest, data in raw.items()}

    def _commit(self, sessions: dict[str, Session]) -> None:
        payload = {digest: encode_session(s) for digest, s in sessions.items()}
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=f".{self._path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self._path)
        except:
            os.unlink(tmp_name)
            raise
        super()._commit(sessions)
