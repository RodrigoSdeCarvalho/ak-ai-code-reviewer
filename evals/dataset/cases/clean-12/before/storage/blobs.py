"""A flat, file-backed blob store: one file per key under a root directory."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")


class InvalidKey(ValueError):
    """Keys are 1-128 characters of letters, digits, '.', '_' or '-', starting with a letter or digit."""


class BlobNotFound(KeyError):
    pass


class BlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise InvalidKey(key)
        return self._root / key

    def put(self, key: str, data: bytes) -> None:
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def size(self, key: str) -> int:
        try:
            return self._path(key).stat().st_size
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def keys(self) -> Iterator[str]:
        for entry in sorted(self._root.iterdir()):
            if entry.is_file():
                yield entry.name
