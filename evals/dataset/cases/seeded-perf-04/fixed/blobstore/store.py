"""Content-addressed blob storage with an append-only name index."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


class BlobNotFound(KeyError):
    """Raised when a name has no live blob."""


@dataclass(frozen=True)
class IndexEntry:
    name: str
    digest: str
    size: int


@dataclass(frozen=True)
class GcReport:
    removed: list[str]
    freed_bytes: int
    kept: int


class BlobStore:
    """Single-writer store: blobs live in `objects/<sha256>`, `index.jsonl` maps names to digests.

    Each attachment worker owns its own root directory; the last index record for a name wins.
    """

    def __init__(self, root: Path) -> None:
        self._objects = root / "objects"
        self._index = root / "index.jsonl"
        self._objects.mkdir(parents=True, exist_ok=True)
        self._index.touch(exist_ok=True)

    def put(self, name: str, data: bytes) -> IndexEntry:
        digest = hashlib.sha256(data).hexdigest()
        target = self._objects / digest
        if not target.exists():
            staging = target.with_suffix(".tmp")
            staging.write_bytes(data)
            staging.replace(target)
        self._append({"name": name, "digest": digest, "size": len(data)})
        return IndexEntry(name, digest, len(data))

    def get(self, name: str) -> bytes:
        return (self._objects / self.stat(name).digest).read_bytes()

    def stat(self, name: str) -> IndexEntry:
        entry = self._live_entries().get(name)
        if entry is None:
            raise BlobNotFound(name)
        return entry

    def delete(self, name: str) -> None:
        self.stat(name)
        self._append({"name": name, "deleted": True})

    def names(self) -> list[str]:
        return sorted(self._live_entries())

    def usage(self) -> int:
        """Bytes referenced by live names, counting shared content once."""
        sizes = {entry.digest: entry.size for entry in self._live_entries().values()}
        return sum(sizes.values())

    def collect_garbage(self) -> GcReport:
        """Delete object files that no live name points to."""
        removed: list[str] = []
        freed = 0
        kept = 0
        live = {entry.digest for entry in self._live_entries().values()}
        for path in sorted(self._objects.iterdir()):
            if path.suffix == ".tmp":
                continue
            if path.name in live:
                kept += 1
                continue
            freed += path.stat().st_size
            path.unlink()
            removed.append(path.name)
        return GcReport(removed=removed, freed_bytes=freed, kept=kept)

    def _append(self, record: dict[str, object]) -> None:
        with self._index.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")

    def _live_entries(self) -> dict[str, IndexEntry]:
        live: dict[str, IndexEntry] = {}
        with self._index.open(encoding="utf-8") as fh:
            for line in fh:
                record = json.loads(line)
                if record.get("deleted"):
                    live.pop(record["name"], None)
                else:
                    live[record["name"]] = IndexEntry(record["name"], record["digest"], record["size"])
        return live
