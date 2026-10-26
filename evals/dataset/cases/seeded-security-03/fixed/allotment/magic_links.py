from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from allotment.mailer import Mailer
from allotment.members import MemberDirectory
from allotment.sessions import Session, SessionStore

LINK_TTL = timedelta(minutes=15)
MAX_PENDING_PER_MEMBER = 3


class LinkRejected(Exception):
    pass


@dataclass(frozen=True)
class PendingLink:
    member_id: int
    created_at: datetime
    expires_at: datetime


class MagicLinkService:
    """Passwordless sign-in: email a one-time link that starts a session when opened."""

    def __init__(
        self,
        members: MemberDirectory,
        sessions: SessionStore,
        mailer: Mailer,
        base_url: str,
        ttl: timedelta = LINK_TTL,
    ) -> None:
        self._members = members
        self._sessions = sessions
        self._mailer = mailer
        self._base_url = base_url.rstrip("/")
        self._ttl = ttl
        self._pending: dict[str, PendingLink] = {}

    def request_link(self, email: str, now: datetime) -> None:
        member = self._members.by_email(email)
        if member is None or not member.active:
            # Same response either way, so the form does not reveal who is a member.
            return
        self._trim_pending(member.id)
        token = secrets.token_urlsafe(32)
        self._pending[token] = PendingLink(member.id, now, now + self._ttl)
        minutes = int(self._ttl.total_seconds() // 60)
        self._mailer.send(
            member.email,
            "Your sign-in link",
            f"Hello {member.name},\n\nOpen this link to sign in to the members' area:\n"
            f"{self._base_url}/login/{token}\n\n"
            f"The link can be used once and expires in {minutes} minutes.",
        )

    def redeem(self, token: str, now: datetime) -> Session:
        link = self._pending.pop(token, None)
        if link is None or now >= link.expires_at:
            raise LinkRejected("this sign-in link is not valid; please request a new one")
        member = self._members.get(link.member_id)
        if member is None or not member.active:
            raise LinkRejected("this account is no longer active")
        return self._sessions.start(member.id, now, method="magic_link")

    def purge_expired(self, now: datetime) -> int:
        expired = [token for token, link in self._pending.items() if link.expires_at <= now]
        for token in expired:
            del self._pending[token]
        return len(expired)

    def pending_count(self, member_id: int) -> int:
        return sum(1 for link in self._pending.values() if link.member_id == member_id)

    def _trim_pending(self, member_id: int) -> None:
        mine = sorted(
            (link.created_at, token) for token, link in self._pending.items() if link.member_id == member_id
        )
        excess = len(mine) - (MAX_PENDING_PER_MEMBER - 1)
        for _, token in mine[: max(excess, 0)]:
            del self._pending[token]
