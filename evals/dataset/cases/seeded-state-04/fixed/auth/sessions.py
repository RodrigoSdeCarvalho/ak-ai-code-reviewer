"""In-memory session store shared by every request thread."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

Clock = Callable[[], datetime]
TokenFactory = Callable[[], str]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class Session:
    token: str
    user_id: str
    expires_at: datetime

    def is_live(self, now: datetime) -> bool:
        return now < self.expires_at


class SessionStore:
    """One active session per user: creating a session replaces the user's previous one."""

    def __init__(
        self,
        ttl: timedelta = timedelta(hours=8),
        clock: Clock = _utcnow,
        token_factory: TokenFactory = _new_token,
    ) -> None:
        self._ttl = ttl
        self._clock = clock
        self._token_factory = token_factory
        self._lock = threading.Lock()
        self._by_token: dict[str, Session] = {}
        self._by_user: dict[str, Session] = {}

    def create(self, user_id: str) -> Session:
        token = self._token_factory()
        with self._lock:
            return self._issue(user_id, token)

    def _issue(self, user_id: str, token: str) -> Session:
        session = Session(token, user_id, self._clock() + self._ttl)
        previous = self._by_user.get(user_id)
        if previous is not None and previous.token != token:
            del self._by_token[previous.token]
        self._by_user[user_id] = session
        self._by_token[token] = session
        return session

    def current(self, user_id: str) -> Session | None:
        """The user's live session, if any."""
        with self._lock:
            session = self._by_user.get(user_id)
        if session is None or not session.is_live(self._clock()):
            return None
        return session

    def login(self, user_id: str) -> Session:
        """Sign in, keeping the token of a live session so other open tabs stay signed in.

        The session's expiry restarts either way.
        """
        with self._lock:
            session = self._by_user.get(user_id)
            live = session is not None and session.is_live(self._clock())
            token = session.token if live else self._token_factory()
            return self._issue(user_id, token)

    def validate(self, token: str) -> Session | None:
        with self._lock:
            session = self._by_token.get(token)
        if session is None or not session.is_live(self._clock()):
            return None
        return session

    def revoke(self, token: str) -> bool:
        with self._lock:
            session = self._by_token.pop(token, None)
            if session is None:
                return False
            if self._by_user.get(session.user_id) is session:
                del self._by_user[session.user_id]
            return True
