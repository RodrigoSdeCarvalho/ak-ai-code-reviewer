"""Blob storage on the local filesystem for single-node deployments of the attachments service."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

KEY_PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
MAX_KEY_LENGTH = 512

DEFAULT_CONTENT_TYPE = "application/octet-stream"
CONTENT_TYPES = {
    ".csv": "text/csv",
    ".json": "application/json",
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".txt": "text/plain",
}


class InvalidKey(ValueError):
    """The key is empty, too long, or has a path segment that is not allowed."""


class BlobNotFound(KeyError):
    """No blob is stored under the requested key."""


@dataclass(frozen=True)
class BlobInfo:
    key: str
    size: int
    content_type: str
    metadata: dict[str, str]


def validate_key(key: str) -> str:
    """Return `key` if every slash-separated segment is a plain file name."""
    if not key or len(key) > MAX_KEY_LENGTH:
        raise InvalidKey(key)
    if not all(KEY_PART_RE.match(part) for part in key.split("/")):
        raise InvalidKey(key)
    return key


def guess_content_type(key: str) -> str:
    return CONTENT_TYPES.get(PurePosixPath(key).suffix.lower(), DEFAULT_CONTENT_TYPE)


class LocalBlobStore:
    """Stores each blob as a file under `root`; keys map to relative paths.

    Metadata lives in a hidden `.<name>.meta.json` file next to the blob.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._root.joinpath(*validate_key(key).split("/"))

    @staticmethod
    def _meta_path(path: Path) -> Path:
        return path.with_name(f".{path.name}.meta.json")

    def put(self, key: str, data: bytes, metadata: Mapping[str, str] | None = None) -> str:
        """Write the metadata file, then the blob, each atomically; return the blob's sha256 etag.

        `content-type` in `metadata` defaults to a guess from the key's extension.
        """
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        stored = {"content-type": guess_content_type(key), **(metadata or {})}
        meta_tmp = path.with_name(f".{path.name}.meta.tmp")
        meta_tmp.write_text(json.dumps(stored, sort_keys=True), encoding="utf-8")
        os.replace(meta_tmp, self._meta_path(path))
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            raise BlobNotFound(key) from None

    def head(self, key: str) -> BlobInfo:
        """Size, content type and user metadata, without reading the blob."""
        path = self._path(key)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            raise BlobNotFound(key) from None
        meta_path = self._meta_path(path)
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        content_type = metadata.pop("content-type", guess_content_type(key))
        return BlobInfo(key, size, content_type, metadata)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError:
            raise BlobNotFound(key) from None
        self._meta_path(path).unlink(missing_ok=True)

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """Keys starting with `prefix`, in sorted order."""
        for path in sorted(self._root.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                key = path.relative_to(self._root).as_posix()
                if key.startswith(prefix):
                    yield key
