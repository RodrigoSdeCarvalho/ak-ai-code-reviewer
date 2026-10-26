"""Parse contact CSV exports."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass

REQUIRED_COLUMNS = ("email", "name")
MIN_PHONE_DIGITS = 7


@dataclass(frozen=True)
class ContactRow:
    line: int
    email: str
    name: str
    phone: str | None = None
    error: str | None = None


def normalise_phone(raw: str | None) -> str | None:
    """Keep digits and a leading '+'; None for an empty value. Raises ValueError if too short."""
    raw = (raw or "").strip()
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < MIN_PHONE_DIGITS:
        raise ValueError(f"phone number {raw!r} is too short")
    return ("+" if raw.startswith("+") else "") + digits


def parse_rows(lines: Iterable[str]) -> list[ContactRow]:
    """Parse CSV lines with a header row. Invalid rows are returned with `error` set."""
    reader = csv.DictReader(lines)
    missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or ())]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    rows: list[ContactRow] = []
    for record in reader:
        line = reader.line_num
        email = (record["email"] or "").strip().lower()
        name = (record["name"] or "").strip()
        if "@" not in email:
            rows.append(ContactRow(line, email, name, error="invalid e-mail address"))
            continue
        if not name:
            rows.append(ContactRow(line, email, name, error="name is empty"))
            continue
        try:
            phone = normalise_phone(record.get("phone"))
        except ValueError as exc:
            rows.append(ContactRow(line, email, name, error=str(exc)))
            continue
        rows.append(ContactRow(line, email, name, phone))
    return rows
