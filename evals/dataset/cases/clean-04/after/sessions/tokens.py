"""Session tokens and the session record."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime

TOKEN_BYTES = 32


@dataclass(frozen=True)
class Session:
    user_id: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return now >= self.expires_at


def new_token() -> str:
    """A fresh URL-safe bearer token handed to the client."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> str:
    """Storage key for a token; the raw token is never kept server-side."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer_token(authorization: str | None) -> str | None:
    """The token from an `Authorization: Bearer <token>` header value, or None."""
    if not authorization:
        return None
    scheme, _, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def encode_session(session: Session) -> dict[str, str]:
    """JSON-ready form of a session."""
    return {
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
    }


def decode_session(data: dict[str, str]) -> Session:
    """Inverse of encode_session."""
    return Session(
        user_id=data["user_id"],
        created_at=datetime.fromisoformat(data["created_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
    )
