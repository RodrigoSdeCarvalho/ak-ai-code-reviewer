import sqlite3
from datetime import date

import pytest
from roster.db import add_volunteer, connect, set_active
from roster.report import contact_sheet_for_query, coverage_gaps, weekday_coverage
from roster.search import VolunteerFilter, parse_filter, search_volunteers


@pytest.fixture
def conn() -> sqlite3.Connection:
    conn = connect()
    add_volunteer(conn, "Siobhan", "O'Brien", "siobhan@harbourmail.org", date(2025, 2, 1),
                  phone="555-0101", skills=("driving", "sorting"), weekdays=("mon", "sat"))
    add_volunteer(conn, "Liam", "O'Neill", "liam@example.com", date(2025, 5, 9),
                  skills=("sorting",), weekdays=("sat",))
    add_volunteer(conn, "Ada", "Obi", "ada@harbourmail.org", date(2024, 11, 20),
                  skills=("driving",), weekdays=("mon", "wed"))
    kasia = add_volunteer(conn, "Kasia", "Nowak", "kasia@example.com", date(2026, 1, 3),
                          skills=("intake",), weekdays=("wed",))
    set_active(conn, kasia, False)
    return conn


def _surnames(conn: sqlite3.Connection, flt: VolunteerFilter) -> list[str]:
    return [v.surname for v in search_volunteers(conn, flt).volunteers]


def test_surname_search_handles_apostrophes(conn):
    assert _surnames(conn, VolunteerFilter(surname_prefix="O'Brien")) == ["O'Brien"]
    assert _surnames(conn, VolunteerFilter(surname_prefix="o'")) == ["O'Brien", "O'Neill"]


def test_contact_sheet_from_search_form(conn):
    sheet = contact_sheet_for_query(conn, {"surname": "O'B", "weekday": "MON"})
    lines = sheet.splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("Siobhan O'Brien")
    assert lines[1].endswith("driving, sorting")


def test_other_filters_and_paging(conn):
    assert _surnames(conn, VolunteerFilter(surname_prefix="Ob")) == ["Obi"]
    assert _surnames(conn, VolunteerFilter(email_domain="harbourmail.org")) == ["O'Brien", "Obi"]
    assert _surnames(conn, VolunteerFilter(skills=("driving",), weekday="mon", sort="joined")) == ["Obi", "O'Brien"]
    assert _surnames(conn, VolunteerFilter(include_inactive=True, sort="newest", limit=2)) == ["Nowak", "O'Neill"]
    page = search_volunteers(conn, VolunteerFilter(limit=2))
    assert page.total == 3 and page.has_more


def test_coverage_and_form_validation(conn):
    assert weekday_coverage(conn, "sorting") == {
        "mon": 1, "tue": 0, "wed": 0, "thu": 0, "fri": 0, "sat": 2, "sun": 0,
    }
    assert coverage_gaps(conn, "driving", 1) == ["tue", "thu", "fri", "sun"]
    with pytest.raises(ValueError):
        parse_filter({"sort": "phone"})
    with pytest.raises(ValueError):
        parse_filter({"limit": "lots"})
