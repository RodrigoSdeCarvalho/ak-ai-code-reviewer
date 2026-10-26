"""Request handlers for sign-in, sign-out and the current user."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any

from auth.sessions import SessionStore

Response = tuple[int, dict[str, Any]]

_UNKNOWN_USER_SALT = os.urandom(16)


@dataclass(frozen=True)
class Account:
    user_id: str
    salt: bytes
    password_hash: bytes
    disabled: bool = False


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 50_000)


class AccountDirectory:
    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}

    def add(self, user_id: str, password: str, salt: bytes) -> Account:
        account = Account(user_id, salt, hash_password(password, salt))
        self._accounts[user_id] = account
        return account

    def get(self, user_id: str) -> Account | None:
        return self._accounts.get(user_id)


def _bearer_token(headers: dict[str, str]) -> str | None:
    scheme, _, token = headers.get("authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def _password_ok(account: Account | None, password: str) -> bool:
    if account is None:
        hash_password(password, _UNKNOWN_USER_SALT)
        return False
    candidate = hash_password(password, account.salt)
    return hmac.compare_digest(candidate, account.password_hash) and not account.disabled


def login(directory: AccountDirectory, store: SessionStore, body: dict[str, Any]) -> Response:
    """POST /login with {"user_id", "password"}."""
    user_id = str(body.get("user_id", ""))
    if not _password_ok(directory.get(user_id), str(body.get("password", ""))):
        return 401, {"error": "invalid credentials"}
    session = store.create(user_id)
    return 200, {"token": session.token, "expires_at": session.expires_at.isoformat()}


def logout(store: SessionStore, headers: dict[str, str]) -> Response:
    """POST /logout with a bearer token."""
    token = _bearer_token(headers)
    if token is None or not store.revoke(token):
        return 401, {"error": "not signed in"}
    return 204, {}


def whoami(store: SessionStore, headers: dict[str, str]) -> Response:
    """GET /me with a bearer token."""
    token = _bearer_token(headers)
    session = store.validate(token) if token else None
    if session is None:
        return 401, {"error": "not signed in"}
    return 200, {"user_id": session.user_id, "expires_at": session.expires_at.isoformat()}
