"""Server-side session storage keyed by token digest."""

from __future__ import annotations

from datetime import datetime, timedelta

from sessions.tokens import Session, new_token, token_digest

DEFAULT_TTL = timedelta(hours=12)


class SessionStore:
    """In-memory sessions for a single application process."""

    def __init__(self, ttl: timedelta = DEFAULT_TTL) -> None:
        if ttl <= timedelta(0):
            raise ValueError("ttl must be positive")
        self._ttl = ttl
        self._sessions: dict[str, Session] = {}

    def create(self, user_id: str, now: datetime) -> str:
        """Start a session for `user_id` and return the bearer token."""
        token = new_token()
        self._sessions[token_digest(token)] = Session(user_id, created_at=now, expires_at=now + self._ttl)
        return token

    def get(self, token: str, now: datetime) -> Session | None:
        """The live session for `token`, or None if unknown or expired."""
        digest = token_digest(token)
        session = self._sessions.get(digest)
        if session is None:
            return None
        if session.is_expired(now):
            del self._sessions[digest]
            return None
        return session

    def revoke(self, token: str) -> bool:
        """End one session; False if it did not exist."""
        return self._sessions.pop(token_digest(token), None) is not None

    def revoke_user(self, user_id: str) -> int:
        """End every session of `user_id` (password change, account lock); returns how many."""
        doomed = [d for d, s in self._sessions.items() if s.user_id == user_id]
        for digest in doomed:
            del self._sessions[digest]
        return len(doomed)

    def purge_expired(self, now: datetime) -> int:
        """Drop expired sessions; returns how many were dropped."""
        expired = [d for d, s in self._sessions.items() if s.is_expired(now)]
        for digest in expired:
            del self._sessions[digest]
        return len(expired)
