"""Session storage backends.

Stores only ever see SHA-256 hashes of the access and refresh tokens, never the tokens themselves.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


class StoreError(Exception):
    """The session store could not be read or written."""


@dataclass(frozen=True)
class SessionRecord:
    access_hash: str
    refresh_hash: str
    user_id: int
    created_at: datetime
    expires_at: datetime
    refresh_expires_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_hash": self.access_hash,
            "refresh_hash": self.refresh_hash,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "refresh_expires_at": self.refresh_expires_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        return cls(
            access_hash=data["access_hash"],
            refresh_hash=data["refresh_hash"],
            user_id=int(data["user_id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            refresh_expires_at=datetime.fromisoformat(data["refresh_expires_at"]),
        )


class SessionStore(Protocol):
    def get(self, access_hash: str) -> SessionRecord | None: ...

    def take_by_refresh(self, refresh_hash: str) -> SessionRecord | None:
        """Remove and return the session holding this refresh hash, atomically."""
        ...

    def all(self) -> list[SessionRecord]: ...

    def save(self, record: SessionRecord) -> None: ...

    def delete(self, access_hash: str) -> None:
        """Remove a session; deleting an unknown session is not an error."""
        ...


class MemorySessionStore:
    """Process-local store for tests and single-process development servers."""

    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def get(self, access_hash: str) -> SessionRecord | None:
        return self._records.get(access_hash)

    def take_by_refresh(self, refresh_hash: str) -> SessionRecord | None:
        with self._lock:
            record = _find_refresh(self._records, refresh_hash)
            if record is not None:
                del self._records[record.access_hash]
            return record

    def all(self) -> list[SessionRecord]:
        with self._lock:
            return list(self._records.values())

    def save(self, record: SessionRecord) -> None:
        with self._lock:
            self._records[record.access_hash] = record

    def delete(self, access_hash: str) -> None:
        with self._lock:
            self._records.pop(access_hash, None)


class FileSessionStore:
    """Keeps every session in one JSON file that is rewritten atomically on each change.

    Meant for a single server process with a modest number of live sessions.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    def get(self, access_hash: str) -> SessionRecord | None:
        return self._read_all().get(access_hash)

    def take_by_refresh(self, refresh_hash: str) -> SessionRecord | None:
        with self._lock:
            records = self._read_all()
            record = _find_refresh(records, refresh_hash)
            if record is not None:
                del records[record.access_hash]
                self._write_all(records)
            return record

    def all(self) -> list[SessionRecord]:
        return list(self._read_all().values())

    def save(self, record: SessionRecord) -> None:
        with self._lock:
            records = self._read_all()
            records[record.access_hash] = record
            self._write_all(records)

    def delete(self, access_hash: str) -> None:
        with self._lock:
            records = self._read_all()
            if records.pop(access_hash, None) is not None:
                self._write_all(records)

    def _read_all(self) -> dict[str, SessionRecord]:
        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise StoreError(f"cannot read {self._path}: {exc}") from exc
        try:
            items = json.loads(text)
            return {item["access_hash"]: SessionRecord.from_dict(item) for item in items}
        except (ValueError, KeyError, TypeError) as exc:
            raise StoreError(f"{self._path} is corrupt: {exc}") from exc

    def _write_all(self, records: dict[str, SessionRecord]) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        payload = json.dumps([record.to_dict() for record in records.values()], indent=1)
        try:
            tmp.write_text(payload, encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            tmp.unlink(missing_ok=True)
            raise StoreError(f"cannot write {self._path}: {exc}") from exc


def _find_refresh(records: dict[str, SessionRecord], refresh_hash: str) -> SessionRecord | None:
    return next((r for r in records.values() if r.refresh_hash == refresh_hash), None)
