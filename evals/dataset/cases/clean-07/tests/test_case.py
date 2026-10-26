import json
import os

import pytest

from attachments.handlers import download, upload
from attachments.store import AttachmentStore, InvalidName, NotFound


@pytest.fixture
def store(tmp_path):
    (tmp_path / "secret.txt").write_text("top secret", encoding="utf-8")
    return AttachmentStore(tmp_path / "files")


def test_round_trip(store):
    created = upload(store, "Invoice.PDF", b"%PDF-1.7 data")
    assert created.status == 201
    name = json.loads(created.body)["name"]
    assert name.endswith(".pdf")
    got = download(store, name)
    assert (got.status, got.body, got.headers["Content-Type"]) == (200, b"%PDF-1.7 data", "application/pdf")


def test_same_content_is_stored_once(store, tmp_path):
    first = json.loads(upload(store, "a.txt", b"hello").body)["name"]
    second = json.loads(upload(store, "b.txt", b"hello").body)["name"]
    assert first == second
    assert len(os.listdir(tmp_path / "files")) == 1


@pytest.mark.parametrize("name", ["../secret.txt", "..", "", ".", "/etc/passwd", "sub/../../secret.txt", "a\x00b.pdf"])
def test_names_outside_the_directory_are_rejected(store, name):
    with pytest.raises(InvalidName):
        store.read(name)
    assert download(store, name).status == 400


def test_absolute_path_to_a_real_file_is_rejected(store, tmp_path):
    assert download(store, str(tmp_path / "secret.txt")).status == 400


def test_dot_segments_that_stay_inside_are_allowed(store):
    name = json.loads(upload(store, "a.txt", b"hi").body)["name"]
    assert download(store, f"x/../{name}").body == b"hi"


def test_missing_file_is_404(store):
    with pytest.raises(NotFound):
        store.read("0" * 64 + ".pdf")
    assert download(store, "0" * 64 + ".pdf").status == 404


def test_relative_root_is_anchored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rel = AttachmentStore(tmp_path.joinpath("x").relative_to(tmp_path))
    name = json.loads(upload(rel, "a.csv", b"1,2").body)["name"]
    monkeypatch.chdir(tmp_path.parent)
    assert download(rel, name).body == b"1,2"


def test_upload_errors(store):
    assert upload(store, "run.exe", b"MZ").status == 415
    assert upload(store, "big.txt", b"x" * (10 * 1024 * 1024 + 1)).status == 413
