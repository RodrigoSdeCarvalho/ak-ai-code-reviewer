import os

import pytest

from storage.blobs import BlobNotFound, BlobStore, InvalidKey


@pytest.fixture
def store(tmp_path):
    return BlobStore(tmp_path / "blobs")


def _files(store_root):
    return sorted(p.name for p in store_root.iterdir())


def test_put_get_and_overwrite(store, tmp_path):
    store.put("report.csv", b"a,b\n1,2\n")
    store.put("report.csv", b"a,b\n3,4\n")
    assert store.get("report.csv") == b"a,b\n3,4\n"
    assert store.size("report.csv") == 8
    assert _files(tmp_path / "blobs") == ["report.csv"]


def test_put_stream_counts_bytes(store):
    assert store.put_stream("big.bin", (bytes([i]) * 1000 for i in range(5))) == 5000
    assert store.get("big.bin")[:1000] == b"\x00" * 1000
    assert store.size("big.bin") == 5000


def test_failed_stream_keeps_previous_blob_and_leaves_no_temp_file(store, tmp_path):
    store.put("data.json", b'{"v": 1}')

    def chunks():
        yield b'{"v": '
        raise ConnectionResetError("client went away")

    with pytest.raises(ConnectionResetError):
        store.put_stream("data.json", chunks())
    assert store.get("data.json") == b'{"v": 1}'
    assert _files(tmp_path / "blobs") == ["data.json"]


def test_failed_first_write_creates_nothing(store, tmp_path):
    def chunks():
        raise RuntimeError("upstream failed")
        yield b""

    with pytest.raises(RuntimeError):
        store.put_stream("new.txt", chunks())
    with pytest.raises(BlobNotFound):
        store.get("new.txt")
    assert _files(tmp_path / "blobs") == []


def test_keys_skip_uploads_in_progress(store, tmp_path):
    store.put("b.txt", b"b")
    store.put("a.txt", b"a")
    (tmp_path / "blobs" / ".incoming-abc123").write_bytes(b"partial")
    assert list(store.keys()) == ["a.txt", "b.txt"]


def test_copy(store, tmp_path):
    store.put("src.bin", b"x" * 3_000_000)
    store.copy("src.bin", "dst.bin")
    assert store.get("dst.bin") == b"x" * 3_000_000
    assert _files(tmp_path / "blobs") == ["dst.bin", "src.bin"]


def test_copy_of_missing_source(store, tmp_path):
    with pytest.raises(BlobNotFound):
        store.copy("nope", "dst.bin")
    assert _files(tmp_path / "blobs") == []


@pytest.mark.parametrize("key", ["", "../escape", ".hidden", ".incoming-x", "a/b", "a\\b", "x" * 129])
def test_invalid_keys_are_rejected(store, key):
    with pytest.raises(InvalidKey):
        store.put(key, b"data")


def test_delete(store):
    store.put("gone.txt", b"bye")
    store.delete("gone.txt")
    with pytest.raises(BlobNotFound):
        store.delete("gone.txt")
    assert list(store.keys()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test_stored_blob_gets_umask_permissions(store, tmp_path):
    previous = os.umask(0o022)
    try:
        store.put("shared.txt", b"readable")
    finally:
        os.umask(previous)
    assert (tmp_path / "blobs" / "shared.txt").stat().st_mode & 0o777 == 0o644
