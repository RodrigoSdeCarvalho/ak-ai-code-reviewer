"""Blob storage on the local filesystem for single-node deployments of the attachments service."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Iterator
from pathlib import Path

KEY_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_KEY_LENGTH = 512


class InvalidKey(ValueError):
    """The key is empty, too long, or has a path segment that is not allowed."""


class BlobNotFound(KeyError):
    """No blob is stored under the requested key."""


def validate_key(key: str) -> str:
    """Return `key` if every slash-separated segment is a plain file name."""
    if not key or len(key) > MAX_KEY_LENGTH:
        raise InvalidKey(key)
    if not all(KEY_PART_RE.match(part) for part in key.split("/")):
        raise InvalidKey(key)
    return key


class LocalBlobStore:
    """Stores each blob as a file under `root`; keys map to relative paths."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root.joinpath(*validate_key(key).split("/"))

    def put(self, key: str, data: bytes) -> str:
        """Write the blob atomically and return its sha256 etag."""
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """Keys starting with `prefix`, in sorted order."""
        for path in sorted(self._root.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                key = path.relative_to(self._root).as_posix()
                if key.startswith(prefix):
                    yield key
