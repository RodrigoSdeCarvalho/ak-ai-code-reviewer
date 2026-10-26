"""SQLite-backed storage for employees, projects and time entries."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from timesheets.models import Employee, Entry, Project, UnknownRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, weekly_capacity TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    hourly_rate TEXT NOT NULL, billable INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY, employee_id INTEGER NOT NULL REFERENCES employees(id),
    project_id INTEGER NOT NULL REFERENCES projects(id), day TEXT NOT NULL, hours TEXT NOT NULL
);
"""


class TimesheetStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def open(cls, path: str = ":memory:") -> TimesheetStore:
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA)
        return cls(conn)

    def add_employee(self, employee: Employee) -> None:
        self._conn.execute(
            "INSERT INTO employees VALUES (?, ?, ?)",
            (employee.id, employee.name, str(employee.weekly_capacity)),
        )

    def add_project(self, project: Project) -> None:
        self._conn.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
            (project.id, project.code, project.name, str(project.hourly_rate), int(project.billable)),
        )

    def add_entry(self, entry: Entry) -> None:
        self._conn.execute(
            "INSERT INTO entries VALUES (?, ?, ?, ?, ?)",
            (entry.id, entry.employee_id, entry.project_id, entry.day.isoformat(), str(entry.hours)),
        )

    def entries_between(self, start: date, end: date) -> list[Entry]:
        rows = self._conn.execute(
            "SELECT id, employee_id, project_id, day, hours FROM entries"
            " WHERE day BETWEEN ? AND ? ORDER BY day, id",
            (start.isoformat(), end.isoformat()),
        )
        return [Entry(r[0], r[1], r[2], date.fromisoformat(r[3]), Decimal(r[4])) for r in rows]

    def employee(self, employee_id: int) -> Employee:
        found = self.employees([employee_id])
        if employee_id not in found:
            raise UnknownRecord(f"employee {employee_id}")
        return found[employee_id]

    def employees(self, ids: Iterable[int]) -> dict[int, Employee]:
        wanted = sorted(set(ids))
        if not wanted:
            return {}
        marks = ",".join("?" * len(wanted))
        rows = self._conn.execute(
            f"SELECT id, name, weekly_capacity FROM employees WHERE id IN ({marks})", wanted
        )
        return {r[0]: Employee(r[0], r[1], Decimal(r[2])) for r in rows}

    def project(self, project_id: int) -> Project:
        found = self.projects([project_id])
        if project_id not in found:
            raise UnknownRecord(f"project {project_id}")
        return found[project_id]

    def projects(self, ids: Iterable[int]) -> dict[int, Project]:
        wanted = sorted(set(ids))
        if not wanted:
            return {}
        marks = ",".join("?" * len(wanted))
        rows = self._conn.execute(
            f"SELECT id, code, name, hourly_rate, billable FROM projects WHERE id IN ({marks})",
            wanted,
        )
        return {r[0]: Project(r[0], r[1], r[2], Decimal(r[3]), bool(r[4])) for r in rows}
