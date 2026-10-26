"""Content-addressed blob storage on the local filesystem."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_KEY_RE = re.compile(r"[0-9a-f]{64}")


class BlobNotFound(KeyError):
    """No blob is stored under the requested key."""


@dataclass(frozen=True)
class BlobInfo:
    key: str
    size: int


def blob_key(data: bytes) -> str:
    """Return the storage key for `data`: its SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


class BlobStore:
    """Stores each blob at `root/<first two key characters>/<key>`."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path_for(self, key: str) -> Path:
        if not _KEY_RE.fullmatch(key):
            raise ValueError(f"invalid blob key: {key!r}")
        return self._root / key[:2] / key

    def put(self, data: bytes) -> BlobInfo:
        """Store `data` and return its key; storing the same bytes twice is a no-op."""
        key = blob_key(data)
        path = self._path_for(key)
        if path.exists():
            return BlobInfo(key, len(data))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return BlobInfo(key, len(data))

    def get(self, key: str) -> bytes:
        try:
            return self._path_for(key).read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def exists(self, key: str) -> bool:
        return self._path_for(key).exists()

    def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink()
        except FileNotFoundError:
            raise BlobNotFound(key) from None
