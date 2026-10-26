from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_TTL = timedelta(days=14)


@dataclass
class Session:
    id: str
    member_id: int
    created_at: datetime
    expires_at: datetime
    method: str = "password"

    def is_valid(self, now: datetime) -> bool:
        return now < self.expires_at


class SessionStore:
    def __init__(self, ttl: timedelta = SESSION_TTL) -> None:
        self._ttl = ttl
        self._sessions: dict[str, Session] = {}

    def start(self, member_id: int, now: datetime, method: str = "password") -> Session:
        session = Session(secrets.token_urlsafe(32), member_id, now, now + self._ttl, method)
        self._sessions[session.id] = session
        return session

    def lookup(self, session_id: str, now: datetime) -> Session | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if not session.is_valid(now):
            del self._sessions[session_id]
            return None
        return session

    def end(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def end_all_for(self, member_id: int) -> int:
        doomed = [sid for sid, s in self._sessions.items() if s.member_id == member_id]
        for sid in doomed:
            del self._sessions[sid]
        return len(doomed)
