"""Attachment files kept in one directory, named by content hash."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 10 * 1024 * 1024
CONTENT_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".txt": "text/plain",
    ".csv": "text/csv",
}


class AttachmentError(Exception):
    """An attachment could not be stored or read."""


class TooLarge(AttachmentError):
    pass


class UnsupportedType(AttachmentError):
    pass


@dataclass(frozen=True)
class StoredFile:
    name: str
    size: int
    sha256: str
    content_type: str


def content_type_for(name: str) -> str:
    return CONTENT_TYPES.get(Path(name).suffix.lower(), "application/octet-stream")


class AttachmentStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, original_name: str) -> StoredFile:
        """Store `data` once per distinct content; returns the stored name and metadata."""
        suffix = Path(original_name).suffix.lower()
        if suffix not in CONTENT_TYPES:
            raise UnsupportedType(f"{suffix or 'no extension'} files are not accepted")
        if len(data) > MAX_BYTES:
            raise TooLarge(f"{len(data)} bytes exceeds the {MAX_BYTES} byte limit")
        digest = hashlib.sha256(data).hexdigest()
        name = f"{digest}{suffix}"
        path = self._root / name
        if not path.exists():
            fd, tmp_name = tempfile.mkstemp(dir=self._root, suffix=".part")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp_name, path)
            except BaseException:
                os.unlink(tmp_name)
                raise
        return StoredFile(name, len(data), digest, CONTENT_TYPES[suffix])

    def read(self, name: str) -> bytes:
        return (self._root / name).read_bytes()
