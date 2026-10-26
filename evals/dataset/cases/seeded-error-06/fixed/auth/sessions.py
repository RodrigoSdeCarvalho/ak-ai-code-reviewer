"""Login sessions: short-lived access tokens plus rotating refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from auth.store import SessionRecord, SessionStore
from auth.users import User, UserDirectory

ACCESS_TTL = timedelta(minutes=30)
REFRESH_TTL = timedelta(days=14)


class InvalidCredentials(Exception):
    """Unknown email, wrong password or deactivated account."""


class InvalidSession(Exception):
    """The token is unknown, expired, already used or belongs to a deactivated user."""


@dataclass(frozen=True)
class IssuedSession:
    """What the client receives at login or refresh. The raw tokens are never stored."""

    access_token: str
    refresh_token: str
    user_id: int
    expires_at: datetime
    refresh_expires_at: datetime


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(32)


class SessionManager:
    def __init__(
        self,
        users: UserDirectory,
        store: SessionStore,
        access_ttl: timedelta = ACCESS_TTL,
        refresh_ttl: timedelta = REFRESH_TTL,
        token_factory: Callable[[], str] = _new_token,
    ) -> None:
        self._users = users
        self._store = store
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl
        self._new_token = token_factory

    def login(self, email: str, password: str, now: datetime) -> IssuedSession:
        user = self._users.check_password(email, password)
        if user is None:
            raise InvalidCredentials()
        return self._issue(user.id, now)

    def authenticate(self, access_token: str, now: datetime) -> User:
        record = self._store.get(token_hash(access_token))
        if record is None or record.expires_at <= now:
            raise InvalidSession()
        user = self._users.get(record.user_id)
        if not user.active:
            raise InvalidSession()
        return user

    def refresh(self, refresh_token: str, now: datetime) -> IssuedSession:
        """Exchange a refresh token for a new session; the old tokens stop working."""
        record = self._store.take_by_refresh(token_hash(refresh_token))
        if record is None or record.refresh_expires_at <= now:
            raise InvalidSession()
        if not self._users.get(record.user_id).active:
            raise InvalidSession()
        return self._issue(record.user_id, now)

    def logout(self, access_token: str) -> None:
        self._store.delete(token_hash(access_token))

    def sign_out_everywhere(self, user_id: int) -> int:
        """End every session of the user and return how many were ended."""
        records = [record for record in self._store.all() if record.user_id == user_id]
        for record in records:
            self._store.delete(record.access_hash)
        return len(records)

    def change_password(self, user_id: int, new_password: str) -> int:
        """Set a new password and end every session of the user."""
        self._users.set_password(user_id, new_password)
        return self.sign_out_everywhere(user_id)

    def purge_expired(self, now: datetime) -> int:
        """Delete sessions whose refresh token has expired; returns how many were deleted."""
        expired = [r for r in self._store.all() if r.refresh_expires_at <= now]
        for record in expired:
            self._store.delete(record.access_hash)
        return len(expired)

    def _issue(self, user_id: int, now: datetime) -> IssuedSession:
        issued = IssuedSession(
            access_token=self._new_token(),
            refresh_token=self._new_token(),
            user_id=user_id,
            expires_at=now + self._access_ttl,
            refresh_expires_at=now + self._refresh_ttl,
        )
        self._store.save(
            SessionRecord(
                access_hash=token_hash(issued.access_token),
                refresh_hash=token_hash(issued.refresh_token),
                user_id=user_id,
                created_at=now,
                expires_at=issued.expires_at,
                refresh_expires_at=issued.refresh_expires_at,
            )
        )
        return issued
