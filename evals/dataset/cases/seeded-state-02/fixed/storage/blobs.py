"""Content-addressed blob storage on the local filesystem."""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_SIZE = 64 * 1024 * 1024


class BlobNotFound(KeyError):
    pass


class BlobTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class BlobInfo:
    digest: str
    size: int
    created: bool


class BlobStore:
    """Stores each blob once, at `<root>/<digest[:2]>/<digest[2:]>`, keyed by its SHA-256."""

    def __init__(self, root: Path, max_size: int = DEFAULT_MAX_SIZE) -> None:
        self._root = root
        self._max_size = max_size
        self._incoming = root / "incoming"
        self._incoming.mkdir(parents=True, exist_ok=True)

    def _path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"not a sha256 hex digest: {digest!r}")
        return self._root / digest[:2] / digest[2:]

    def put(self, data: bytes) -> BlobInfo:
        return self.put_stream([data])

    def put_stream(self, chunks: Iterable[bytes]) -> BlobInfo:
        """Store a blob delivered in chunks without holding it in memory."""
        hasher = hashlib.sha256()
        size = 0
        incoming = self._incoming / f"upload-{uuid.uuid4().hex}"
        try:
            with incoming.open("xb") as out:
                for chunk in chunks:
                    size += len(chunk)
                    if size > self._max_size:
                        raise BlobTooLarge(f"blob exceeds {self._max_size} bytes")
                    hasher.update(chunk)
                    out.write(chunk)
        except BaseException:
            incoming.unlink(missing_ok=True)
            raise
        digest = hasher.hexdigest()
        target = self._path_for(digest)
        try:
            if target.exists():
                return BlobInfo(digest, size, created=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(incoming, target)
        finally:
            incoming.unlink(missing_ok=True)
        return BlobInfo(digest, size, created=True)

    def exists(self, digest: str) -> bool:
        return self._path_for(digest).exists()

    def get(self, digest: str) -> bytes:
        path = self._path_for(digest)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(digest) from None

    def delete(self, digest: str) -> bool:
        try:
            self._path_for(digest).unlink()
        except FileNotFoundError:
            return False
        return True
