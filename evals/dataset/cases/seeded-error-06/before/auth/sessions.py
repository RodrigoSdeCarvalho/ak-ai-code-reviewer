"""Login sessions kept in process memory."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from auth.users import User, UserDirectory

SESSION_TTL = timedelta(hours=12)


class InvalidCredentials(Exception):
    """Unknown email, wrong password or deactivated account."""


class InvalidSession(Exception):
    """The session token is unknown, expired or belongs to a deactivated user."""


@dataclass(frozen=True)
class Session:
    token: str
    user_id: int
    created_at: datetime
    expires_at: datetime


def _new_token() -> str:
    return secrets.token_urlsafe(32)


class SessionManager:
    def __init__(
        self,
        users: UserDirectory,
        ttl: timedelta = SESSION_TTL,
        token_factory: Callable[[], str] = _new_token,
    ) -> None:
        self._users = users
        self._ttl = ttl
        self._new_token = token_factory
        self._sessions: dict[str, Session] = {}

    def login(self, email: str, password: str, now: datetime) -> Session:
        user = self._users.check_password(email, password)
        if user is None:
            raise InvalidCredentials()
        session = Session(self._new_token(), user.id, now, now + self._ttl)
        self._sessions[session.token] = session
        return session

    def authenticate(self, token: str, now: datetime) -> User:
        session = self._sessions.get(token)
        if session is None or session.expires_at <= now:
            self._sessions.pop(token, None)
            raise InvalidSession()
        user = self._users.get(session.user_id)
        if not user.active:
            raise InvalidSession()
        return user

    def logout(self, token: str) -> None:
        self._sessions.pop(token, None)

    def change_password(self, user_id: int, new_password: str) -> None:
        """Set a new password and end every session of the user."""
        self._users.set_password(user_id, new_password)
        for token in [t for t, s in self._sessions.items() if s.user_id == user_id]:
            del self._sessions[token]
