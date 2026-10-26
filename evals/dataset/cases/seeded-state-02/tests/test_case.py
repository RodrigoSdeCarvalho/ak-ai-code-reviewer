import hashlib

import pytest

from storage.blobs import BlobStore, BlobTooLarge


def _leftovers(root):
    return [p.name for p in (root / "incoming").iterdir()]


def test_duplicate_upload_leaves_no_staging_file(tmp_path):
    store = BlobStore(tmp_path)
    first = store.put_stream([b"hello ", b"world"])
    second = store.put_stream([b"hello world"])
    assert first.created and not second.created
    assert first.digest == second.digest
    assert _leftovers(tmp_path) == []


def test_repeated_put_of_same_bytes_keeps_staging_empty(tmp_path):
    store = BlobStore(tmp_path)
    for _ in range(5):
        store.put(b"same payload")
    assert _leftovers(tmp_path) == []


def test_new_blob_round_trip_and_size_limit(tmp_path):
    store = BlobStore(tmp_path, max_size=10)
    info = store.put_stream([b"abc", b"def"])
    assert info.digest == hashlib.sha256(b"abcdef").hexdigest()
    assert info.size == 6 and info.created
    assert store.get(info.digest) == b"abcdef"
    with pytest.raises(BlobTooLarge):
        store.put_stream([b"0123456", b"789ab"])
    assert _leftovers(tmp_path) == []
