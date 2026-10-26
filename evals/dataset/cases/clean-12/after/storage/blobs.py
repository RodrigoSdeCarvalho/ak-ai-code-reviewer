"""A flat, file-backed blob store: one file per key under a root directory."""

from __future__ import annotations

import os
import re
import shutil
import uuid
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_TEMP_PREFIX = ".incoming-"
_COPY_CHUNK = 1024 * 1024


class InvalidKey(ValueError):
    """Keys are 1-128 characters of letters, digits, '.', '_' or '-', starting with a letter or digit."""


class BlobNotFound(KeyError):
    pass


@contextmanager
def _atomic_write(target: Path) -> Iterator[IO[bytes]]:
    """Yield a temporary file next to `target`; it replaces `target` only if the block completes."""
    temp_path = target.with_name(f"{_TEMP_PREFIX}{uuid.uuid4().hex}")
    handle = temp_path.open("xb")
    try:
        with handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


class BlobStore:
    """Writes are atomic: a reader sees either the previous blob or the complete new one, never a partial file."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise InvalidKey(key)
        return self._root / key

    def put(self, key: str, data: bytes) -> None:
        with _atomic_write(self._path(key)) as handle:
            handle.write(data)

    def put_stream(self, key: str, chunks: Iterable[bytes]) -> int:
        """Store the concatenation of `chunks` under `key`. Returns the number of bytes written."""
        written = 0
        with _atomic_write(self._path(key)) as handle:
            for chunk in chunks:
                handle.write(chunk)
                written += len(chunk)
        return written

    def copy(self, source_key: str, target_key: str) -> None:
        target = self._path(target_key)
        try:
            source = self._path(source_key).open("rb")
        except FileNotFoundError:
            raise BlobNotFound(source_key) from None
        with source, _atomic_write(target) as handle:
            shutil.copyfileobj(source, handle, _COPY_CHUNK)

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
        """Stored keys in sorted order; uploads still in progress are not listed."""
        for entry in sorted(self._root.iterdir()):
            if entry.is_file() and _KEY.fullmatch(entry.name):
                yield entry.name
