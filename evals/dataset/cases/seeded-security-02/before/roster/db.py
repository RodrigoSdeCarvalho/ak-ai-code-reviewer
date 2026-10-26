from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

SCHEMA = """
CREATE TABLE IF NOT EXISTS volunteers (
    id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    surname TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    joined_on TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS volunteer_skills (
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    skill TEXT NOT NULL,
    PRIMARY KEY (volunteer_id, skill)
);
CREATE TABLE IF NOT EXISTS availability (
    volunteer_id INTEGER NOT NULL REFERENCES volunteers(id),
    weekday TEXT NOT NULL,
    PRIMARY KEY (volunteer_id, weekday)
);
"""


@dataclass(frozen=True)
class Volunteer:
    id: int
    first_name: str
    surname: str
    email: str
    phone: str | None
    joined_on: date
    active: bool

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.surname}"


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def row_to_volunteer(row: sqlite3.Row) -> Volunteer:
    return Volunteer(
        id=row["id"],
        first_name=row["first_name"],
        surname=row["surname"],
        email=row["email"],
        phone=row["phone"],
        joined_on=date.fromisoformat(row["joined_on"]),
        active=bool(row["active"]),
    )


def add_volunteer(
    conn: sqlite3.Connection,
    first_name: str,
    surname: str,
    email: str,
    joined_on: date,
    *,
    phone: str | None = None,
    skills: tuple[str, ...] = (),
    weekdays: tuple[str, ...] = (),
) -> int:
    unknown = set(weekdays) - set(WEEKDAYS)
    if unknown:
        raise ValueError(f"unknown weekdays: {sorted(unknown)}")
    with conn:
        cur = conn.execute(
            "INSERT INTO volunteers (first_name, surname, email, phone, joined_on) VALUES (?, ?, ?, ?, ?)",
            (first_name.strip(), surname.strip(), email.strip().lower(), phone, joined_on.isoformat()),
        )
        volunteer_id = int(cur.lastrowid)
        conn.executemany(
            "INSERT INTO volunteer_skills (volunteer_id, skill) VALUES (?, ?)",
            [(volunteer_id, s.strip().lower()) for s in skills],
        )
        conn.executemany(
            "INSERT INTO availability (volunteer_id, weekday) VALUES (?, ?)",
            [(volunteer_id, d) for d in weekdays],
        )
    return volunteer_id


def get_volunteer(conn: sqlite3.Connection, volunteer_id: int) -> Volunteer | None:
    row = conn.execute("SELECT * FROM volunteers WHERE id = ?", (volunteer_id,)).fetchone()
    return row_to_volunteer(row) if row else None


def set_active(conn: sqlite3.Connection, volunteer_id: int, active: bool) -> None:
    with conn:
        conn.execute("UPDATE volunteers SET active = ? WHERE id = ?", (int(active), volunteer_id))


def list_active(conn: sqlite3.Connection) -> list[Volunteer]:
    rows = conn.execute("SELECT * FROM volunteers WHERE active = 1 ORDER BY surname, first_name").fetchall()
    return [row_to_volunteer(r) for r in rows]
