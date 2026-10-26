from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from roster.db import WEEKDAYS, Volunteer, row_to_volunteer

SORT_ORDERS = {
    "surname": "v.surname COLLATE NOCASE, v.first_name COLLATE NOCASE, v.id",
    "joined": "v.joined_on, v.id",
    "newest": "v.joined_on DESC, v.id DESC",
}
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class VolunteerFilter:
    surname_prefix: str | None = None
    email_domain: str | None = None
    skills: tuple[str, ...] = ()
    weekday: str | None = None
    include_inactive: bool = False
    sort: str = "surname"
    limit: int = 50
    offset: int = 0

    def validate(self) -> None:
        if self.sort not in SORT_ORDERS:
            raise ValueError(f"unknown sort order {self.sort!r}; expected one of {sorted(SORT_ORDERS)}")
        if self.weekday is not None and self.weekday not in WEEKDAYS:
            raise ValueError(f"unknown weekday {self.weekday!r}")
        if not 1 <= self.limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        if self.offset < 0:
            raise ValueError("offset must not be negative")


@dataclass(frozen=True)
class SearchPage:
    volunteers: list[Volunteer]
    total: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.volunteers) < self.total


def parse_filter(query: Mapping[str, str]) -> VolunteerFilter:
    """Build a filter from the coordinators' search form (all values arrive as strings)."""
    skills = tuple(s for s in (part.strip() for part in query.get("skills", "").split(",")) if s)
    try:
        limit = int(query.get("limit", "50"))
        offset = int(query.get("offset", "0"))
    except ValueError:
        raise ValueError("limit and offset must be whole numbers") from None
    flt = VolunteerFilter(
        surname_prefix=query.get("surname") or None,
        email_domain=query.get("email_domain") or None,
        skills=skills,
        weekday=(query.get("weekday") or "").lower() or None,
        include_inactive=query.get("include_inactive", "") in {"1", "true", "yes"},
        sort=query.get("sort", "surname"),
        limit=limit,
        offset=offset,
    )
    flt.validate()
    return flt


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _where(flt: VolunteerFilter) -> tuple[str, list[object]]:
    clauses: list[str] = []
    params: list[object] = []
    if not flt.include_inactive:
        clauses.append("v.active = 1")
    if flt.surname_prefix:
        clauses.append(f"v.surname LIKE '{flt.surname_prefix.strip()}%'")
    if flt.email_domain:
        clauses.append("v.email LIKE ? ESCAPE '\\'")
        params.append("%@" + _escape_like(flt.email_domain.strip().lower()))
    for skill in flt.skills:
        clauses.append("EXISTS (SELECT 1 FROM volunteer_skills s WHERE s.volunteer_id = v.id AND s.skill = ?)")
        params.append(skill.strip().lower())
    if flt.weekday:
        clauses.append("EXISTS (SELECT 1 FROM availability a WHERE a.volunteer_id = v.id AND a.weekday = ?)")
        params.append(flt.weekday)
    return (" AND ".join(clauses) or "1 = 1"), params


def search_volunteers(conn: sqlite3.Connection, flt: VolunteerFilter) -> SearchPage:
    flt.validate()
    where, params = _where(flt)
    total = conn.execute(f"SELECT COUNT(*) FROM volunteers v WHERE {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT v.* FROM volunteers v WHERE {where} ORDER BY {SORT_ORDERS[flt.sort]} LIMIT ? OFFSET ?",
        [*params, flt.limit, flt.offset],
    ).fetchall()
    return SearchPage([row_to_volunteer(r) for r in rows], int(total), flt.offset)


def skills_for(conn: sqlite3.Connection, volunteer_ids: Iterable[int]) -> dict[int, list[str]]:
    ids = sorted(set(volunteer_ids))
    if not ids:
        return {}
    placeholders = ", ".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT volunteer_id, skill FROM volunteer_skills WHERE volunteer_id IN ({placeholders}) ORDER BY skill",
        ids,
    ).fetchall()
    found: dict[int, list[str]] = {}
    for row in rows:
        found.setdefault(row["volunteer_id"], []).append(row["skill"])
    return found
