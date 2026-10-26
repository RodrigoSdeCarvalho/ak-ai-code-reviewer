from __future__ import annotations

from datetime import datetime

from bookclub.models import JournalEntry, User
from bookclub.store import EntryStore

MAX_BODY_CHARS = 20_000


def _require_owner(entry: JournalEntry, user: User) -> None:
    if entry.owner_id != user.id:
        raise PermissionError(f"user {user.id} does not own journal entry {entry.id}")


def _require_reader(entry: JournalEntry, user: User) -> None:
    if entry.owner_id != user.id and user.id not in entry.readers:
        raise PermissionError(f"user {user.id} cannot view journal entry {entry.id}")


def _clean_body(body: str) -> str:
    body = body.strip()
    if not body:
        raise ValueError("journal entry body must not be empty")
    if len(body) > MAX_BODY_CHARS:
        raise ValueError(f"journal entry body is longer than {MAX_BODY_CHARS} characters")
    return body


def create_entry(store: EntryStore, user: User, book_title: str, body: str, now: datetime) -> JournalEntry:
    title = book_title.strip()
    if not title:
        raise ValueError("book title must not be empty")
    return store.create(user.id, title, _clean_body(body), now)


def view_entry(store: EntryStore, user: User, entry_id: int) -> JournalEntry:
    entry = store.get(entry_id)
    _require_reader(entry, user)
    return entry


def edit_entry(store: EntryStore, user: User, entry_id: int, body: str, now: datetime) -> JournalEntry:
    entry = store.get(entry_id)
    _require_owner(entry, user)
    entry.body = _clean_body(body)
    entry.updated_at = now
    return entry


def share_entry(store: EntryStore, user: User, entry_id: int, reader_id: int) -> JournalEntry:
    entry = store.get(entry_id)
    _require_owner(entry, user)
    if reader_id != user.id:
        entry.readers.add(reader_id)
    return entry


def unshare_entry(store: EntryStore, user: User, entry_id: int, reader_id: int) -> JournalEntry:
    entry = store.get(entry_id)
    _require_owner(entry, user)
    entry.readers.discard(reader_id)
    return entry


def list_entries(store: EntryStore, user: User) -> dict[str, list[dict[str, object]]]:
    return {
        "mine": [e.summary() for e in store.owned_by(user.id)],
        "shared_with_me": [e.summary() for e in store.shared_with(user.id)],
    }
