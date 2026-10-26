"""User accounts and password verification."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

DEFAULT_ITERATIONS = 200_000


class UnknownUser(KeyError):
    """No user has the requested id."""


@dataclass
class User:
    id: int
    email: str
    password_hash: bytes
    salt: bytes
    active: bool = True


class UserDirectory:
    def __init__(self, iterations: int = DEFAULT_ITERATIONS) -> None:
        self._iterations = iterations
        self._users: dict[int, User] = {}
        self._by_email: dict[str, int] = {}
        self._next_id = 1

    def create(self, email: str, password: str) -> User:
        email = email.strip().lower()
        if email in self._by_email:
            raise ValueError(f"{email} is already registered")
        salt = secrets.token_bytes(16)
        user = User(self._next_id, email, self._hash(password, salt), salt)
        self._users[user.id] = user
        self._by_email[email] = user.id
        self._next_id += 1
        return user

    def get(self, user_id: int) -> User:
        try:
            return self._users[user_id]
        except KeyError:
            raise UnknownUser(user_id) from None

    def check_password(self, email: str, password: str) -> User | None:
        """Return the active user with these credentials, or None."""
        user_id = self._by_email.get(email.strip().lower())
        if user_id is None:
            return None
        user = self._users[user_id]
        if not user.active:
            return None
        if not hmac.compare_digest(user.password_hash, self._hash(password, user.salt)):
            return None
        return user

    def set_password(self, user_id: int, password: str) -> None:
        user = self.get(user_id)
        user.salt = secrets.token_bytes(16)
        user.password_hash = self._hash(password, user.salt)

    def deactivate(self, user_id: int) -> None:
        self.get(user_id).active = False

    def _hash(self, password: str, salt: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, self._iterations)
