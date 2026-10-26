import pytest

from blobstore.store import BlobNotFound, InvalidKey, LocalBlobStore


def test_content_type_is_guessed_per_blob(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    store.put("tenant-1/logo.png", b"\x89PNG")
    store.put("tenant-1/export.csv", b"id,total\n1,10\n")
    store.put("tenant-2/notes", b"plain bytes")
    assert store.head("tenant-1/logo.png").content_type == "image/png"
    assert store.head("tenant-1/export.csv").content_type == "text/csv"
    assert store.head("tenant-2/notes").content_type == "application/octet-stream"


def test_metadata_does_not_carry_over_between_uploads(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    store.put("a/invoice.pdf", b"%PDF-1.7", {"owner": "u1"})
    store.put("b/invoice.pdf", b"%PDF-1.7")
    assert store.head("a/invoice.pdf").metadata == {"owner": "u1"}
    assert store.head("b/invoice.pdf").metadata == {}


def test_explicit_content_type_and_metadata_round_trip(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    etag = store.put("docs/readme", b"hello", {"content-type": "text/markdown", "owner": "u7"})
    info = store.head("docs/readme")
    assert (info.size, info.content_type, info.metadata) == (5, "text/markdown", {"owner": "u7"})
    assert etag == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert store.get("docs/readme") == b"hello"


def test_listing_hides_metadata_files_and_delete_removes_them(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    store.put("x/one.txt", b"1")
    store.put("x/two.json", b"{}")
    assert list(store.list_keys("x/")) == ["x/one.txt", "x/two.json"]
    store.delete("x/one.txt")
    assert sorted(p.name for p in (tmp_path / "blobs" / "x").iterdir()) == [".two.json.meta.json", "two.json"]
    with pytest.raises(BlobNotFound):
        store.head("x/one.txt")


def test_blob_without_metadata_file_falls_back_to_guess(tmp_path):
    root = tmp_path / "blobs"
    (root / "old").mkdir(parents=True)
    (root / "old" / "photo.jpg").write_bytes(b"jpeg")
    info = LocalBlobStore(root).head("old/photo.jpg")
    assert (info.content_type, info.metadata) == ("image/jpeg", {})


def test_invalid_keys_are_rejected(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    for key in ("", "../escape.txt", "a//b", ".hidden"):
        with pytest.raises(InvalidKey):
            store.put(key, b"x")
