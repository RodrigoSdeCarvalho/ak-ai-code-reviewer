"""Import contacts from CSV into an address book."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from contacts.book import AddressBook
from contacts.parsing import parse_rows

DEFAULT_MAX_ERRORS = 100


class TooManyErrors(Exception):
    def __init__(self, rejected: list[tuple[int, str]]) -> None:
        super().__init__(f"{len(rejected)} invalid rows; nothing was imported")
        self.rejected = rejected


@dataclass
class ImportReport:
    created: int = 0
    updated: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)


def import_csv(book: AddressBook, text: str | Iterable[str], max_errors: int = DEFAULT_MAX_ERRORS) -> ImportReport:
    """Import every valid row of the CSV `text` (a string, or lines such as an open file) into `book`.

    If more than `max_errors` rows are invalid the file is assumed to be the wrong export, and
    TooManyErrors is raised before anything is written.
    """
    lines = text.splitlines() if isinstance(text, str) else text
    rows = parse_rows(lines)
    rejected = [(row.line, row.error) for row in rows if row.error]
    if len(rejected) > max_errors:
        raise TooManyErrors(rejected)
    report = ImportReport(rejected=rejected)
    for row in rows:
        if row.error:
            continue
        if book.upsert(row.email, row.name, row.phone):
            report.created += 1
        else:
            report.updated += 1
    return report
