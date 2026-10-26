from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import replace

from roster.db import WEEKDAYS
from roster.search import VolunteerFilter, parse_filter, search_volunteers, skills_for

COLUMNS = (("Name", 28), ("Email", 32), ("Phone", 14), ("Skills", 0))


def _row(values: tuple[str, ...]) -> str:
    cells = [value.ljust(width) if width else value for value, (_, width) in zip(values, COLUMNS, strict=True)]
    return " ".join(cells).rstrip()


def weekday_coverage(conn: sqlite3.Connection, skill: str | None = None) -> dict[str, int]:
    """Number of active volunteers available on each weekday, optionally only those with `skill`."""
    base = VolunteerFilter(skills=(skill,) if skill else (), limit=1)
    return {day: search_volunteers(conn, replace(base, weekday=day)).total for day in WEEKDAYS}


def coverage_gaps(conn: sqlite3.Connection, skill: str, minimum: int) -> list[str]:
    """Weekdays on which fewer than `minimum` active volunteers with `skill` are available."""
    return [day for day, count in weekday_coverage(conn, skill).items() if count < minimum]


def contact_sheet(conn: sqlite3.Connection, flt: VolunteerFilter) -> str:
    page = search_volunteers(conn, flt)
    skills = skills_for(conn, (v.id for v in page.volunteers))
    lines = [_row(tuple(name for name, _ in COLUMNS))]
    for v in page.volunteers:
        lines.append(_row((v.full_name, v.email, v.phone or "-", ", ".join(skills.get(v.id, [])) or "-")))
    if page.has_more:
        remaining = page.total - page.offset - len(page.volunteers)
        lines.append(f"... and {remaining} more")
    if not page.volunteers:
        lines.append("(no volunteers match)")
    return "\n".join(lines)


def contact_sheet_for_query(conn: sqlite3.Connection, query: Mapping[str, str]) -> str:
    return contact_sheet(conn, parse_filter(query))
