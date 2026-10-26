from datetime import datetime

import pytest

from storage import blobs
from storage.blobs import BlobStore, blob_key
from storage.uploads import AttachmentService

NOW = datetime(2026, 3, 1, 12, 0)


def _disk_full(src: object, dst: object) -> None:
    raise OSError(28, "No space left on device")


def test_put_round_trip_leaves_no_temp_files(tmp_path):
    store = BlobStore(tmp_path)
    info = store.put(b"hello")
    assert info.key == blob_key(b"hello")
    assert info.size == 5
    assert store.get(info.key) == b"hello"
    assert store.put(b"hello") == info
    assert list(tmp_path.rglob("*.tmp")) == []


def test_failed_write_is_reported_to_the_caller(tmp_path, monkeypatch):
    store = BlobStore(tmp_path)
    monkeypatch.setattr(blobs.os, "replace", _disk_full)
    with pytest.raises(OSError):
        store.put(b"quarterly report")
    assert list(tmp_path.rglob("*.tmp")) == []
    assert not store.exists(blob_key(b"quarterly report"))


def test_failed_upload_is_not_indexed(tmp_path, monkeypatch):
    service = AttachmentService(BlobStore(tmp_path))
    monkeypatch.setattr(blobs.os, "replace", _disk_full)
    with pytest.raises(OSError):
        service.upload("report.pdf", b"%PDF-1.7 body", NOW)
    monkeypatch.undo()
    attachment = service.upload("report.pdf", b"%PDF-1.7 body", NOW)
    assert attachment.id == 1
    assert service.download(1) == (attachment, b"%PDF-1.7 body")
