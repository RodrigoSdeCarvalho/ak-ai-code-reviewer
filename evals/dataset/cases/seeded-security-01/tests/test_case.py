from datetime import datetime

import pytest
from bookclub.handlers import (
    create_entry,
    delete_entry,
    leave_entry,
    list_entries,
    share_entry,
    view_entry,
)
from bookclub.models import NotFound, User
from bookclub.store import EntryStore

NOW = datetime(2026, 3, 14, 18, 30)
ALICE = User(1, "Alice")
BOB = User(2, "Bob")
CAROL = User(3, "Carol")


def _shared_entry() -> tuple[EntryStore, int]:
    store = EntryStore()
    entry = create_entry(store, ALICE, "Middlemarch", "Dorothea's chapter on the honeymoon in Rome.", NOW)
    share_entry(store, ALICE, entry.id, BOB.id)
    return store, entry.id


def test_reader_cannot_delete_a_shared_entry():
    store, entry_id = _shared_entry()
    with pytest.raises(PermissionError):
        delete_entry(store, BOB, entry_id)
    assert view_entry(store, ALICE, entry_id).book_title == "Middlemarch"


def test_stranger_cannot_delete():
    store, entry_id = _shared_entry()
    with pytest.raises(PermissionError):
        delete_entry(store, CAROL, entry_id)


def test_owner_deletes_entry():
    store, entry_id = _shared_entry()
    assert delete_entry(store, ALICE, entry_id) == {"deleted": entry_id, "former_readers": [BOB.id]}
    with pytest.raises(NotFound):
        view_entry(store, ALICE, entry_id)
    assert list_entries(store, BOB)["shared_with_me"] == []


def test_reader_leaves_shared_entry():
    store, entry_id = _shared_entry()
    leave_entry(store, BOB, entry_id)
    assert list_entries(store, BOB)["shared_with_me"] == []
    with pytest.raises(PermissionError):
        view_entry(store, BOB, entry_id)
    with pytest.raises(ValueError):
        leave_entry(store, ALICE, entry_id)
