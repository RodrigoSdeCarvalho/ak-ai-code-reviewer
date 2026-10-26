import pytest
from contacts.book import AddressBook
from contacts.importer import TooManyErrors, import_csv

CSV = (
    "email,name,phone\n"
    "Ana@Example.com,Ana Lima,+55 (11) 98765-4321\n"
    "not-an-email,Nobody,\n"
    "ben@example.com,Ben Ortiz,\n"
    "cy@example.com,Cy,12\n"
)


def test_valid_rows_are_imported():
    book = AddressBook()
    report = import_csv(book, CSV)
    assert report.created == 2
    assert report.rejected == [(3, "invalid e-mail address"), (5, "phone number '12' is too short")]
    assert book.get("ana@example.com").phone == "+5511987654321"
    assert book.get("ben@example.com").name == "Ben Ortiz"


def test_import_from_open_file_updates_existing_contacts(tmp_path):
    book = AddressBook()
    book.upsert("ben@example.com", "Ben O.", "5550001234")
    path = tmp_path / "export.csv"
    path.write_text("﻿" + CSV, encoding="utf-8")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        report = import_csv(book, handle)
    assert (report.created, report.updated) == (1, 1)
    assert book.get("ben@example.com") is not None
    assert book.get("ben@example.com").name == "Ben Ortiz"
    assert book.get("ben@example.com").phone == "5550001234"


def test_too_many_errors_writes_nothing():
    book = AddressBook()
    with pytest.raises(TooManyErrors) as excinfo:
        import_csv(book, CSV.splitlines(), max_errors=1)
    assert len(excinfo.value.rejected) == 2
    assert len(book) == 0


def test_missing_column_is_rejected():
    with pytest.raises(ValueError, match="missing columns: name"):
        import_csv(AddressBook(), ["email,phone", "a@example.com,"])
