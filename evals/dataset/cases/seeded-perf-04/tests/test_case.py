import hashlib
from pathlib import Path

import pytest
from blobstore.store import BlobNotFound, BlobStore


@pytest.fixture
def index_reads(monkeypatch):
    reads: list[str] = []
    original_open = Path.open

    def counting_open(self, mode="r", *args, **kwargs):
        if self.name == "index.jsonl" and mode.startswith("r"):
            reads.append(mode)
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    return reads


def _filled(root: Path, count: int) -> BlobStore:
    store = BlobStore(root)
    for i in range(count):
        store.put(f"doc-{i:03d}.txt", f"attachment body {i}\n".encode() * (i + 1))
    return store


def test_garbage_collection_reads_the_index_a_bounded_number_of_times(tmp_path, index_reads):
    store = _filled(tmp_path, 60)
    for i in range(0, 60, 2):
        store.delete(f"doc-{i:03d}.txt")
    index_reads.clear()
    report = store.collect_garbage()
    assert len(report.removed) == 30
    assert len(index_reads) <= 2


def test_collect_garbage_keeps_shared_and_live_content(tmp_path):
    store = BlobStore(tmp_path)
    shared = store.put("a.txt", b"same bytes")
    store.put("b.txt", b"same bytes")
    gone = store.put("c.txt", b"to be deleted")
    store.put("d.txt", b"old version")
    store.put("d.txt", b"new version")
    store.delete("a.txt")
    store.delete("c.txt")
    (tmp_path / "objects" / "partial.tmp").write_bytes(b"in flight")

    report = store.collect_garbage()

    assert sorted(report.removed) == sorted([gone.digest, hashlib.sha256(b"old version").hexdigest()])
    assert report.freed_bytes == len(b"to be deleted") + len(b"old version")
    assert report.kept == 2
    assert store.get("b.txt") == b"same bytes"
    assert store.stat("b.txt").digest == shared.digest
    assert store.get("d.txt") == b"new version"
    assert (tmp_path / "objects" / "partial.tmp").exists()
    with pytest.raises(BlobNotFound):
        store.get("c.txt")
    assert store.names() == ["b.txt", "d.txt"]
    assert store.usage() == len(b"same bytes") + len(b"new version")
