"""Content-addressed blob storage on the local filesystem."""

from __future__ import annotations

import hashlib
import os
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
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, digest: str) -> Path:
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"not a sha256 hex digest: {digest!r}")
        return self._root / digest[:2] / digest[2:]

    def put(self, data: bytes) -> BlobInfo:
        if len(data) > self._max_size:
            raise BlobTooLarge(f"blob exceeds {self._max_size} bytes")
        digest = hashlib.sha256(data).hexdigest()
        target = self._path_for(digest)
        if target.exists():
            return BlobInfo(digest, len(data), created=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        partial.write_bytes(data)
        os.replace(partial, target)
        return BlobInfo(digest, len(data), created=True)

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
