from datetime import date, timedelta
from decimal import Decimal

from timesheets.models import Employee, Entry, Period, Project
from timesheets.report import build_report, render
from timesheets.repository import TimesheetStore

PERIOD = Period(date(2026, 3, 2), date(2026, 3, 29))


def _store() -> TimesheetStore:
    store = TimesheetStore.open()
    for i, name in enumerate(["Ana", "Bruno", "Carla", "Diego", "Eva"], start=1):
        store.add_employee(Employee(i, name, Decimal("40")))
    store.add_project(Project(1, "ACME-WEB", "Acme web shop", Decimal("120.00")))
    store.add_project(Project(2, "ACME-APP", "Acme mobile app", Decimal("135.50")))
    store.add_project(Project(3, "GLOBEX", "Globex data platform", Decimal("99.90")))
    store.add_project(Project(4, "INTERNAL", "Internal tooling", Decimal("0"), billable=False))
    entry_id = 1
    for day in PERIOD:
        if day.weekday() >= 5:
            continue
        for employee_id in range(1, 6):
            for slot in range(4):
                project_id = slot + 1
                hours = Decimal("1.5") if project_id == 4 else Decimal("2.5")
                store.add_entry(Entry(entry_id, employee_id, project_id, day, hours))
                entry_id += 1
    store.add_entry(Entry(entry_id, 1, 1, PERIOD.end + timedelta(days=1), Decimal("8")))
    return store


def _project_queries(store: TimesheetStore) -> list[str]:
    statements: list[str] = []
    store._conn.set_trace_callback(lambda sql: statements.append(sql) if "FROM projects" in sql else None)
    return statements


def test_project_lookups_do_not_scale_with_entries():
    store = _store()
    statements = _project_queries(store)
    report = build_report(store, PERIOD)
    assert report.total_hours == Decimal("900.0")
    assert len(statements) <= 2


def test_billing_totals_per_project():
    report = build_report(_store(), PERIOD)
    assert [line.project.code for line in report.projects] == ["ACME-APP", "ACME-WEB", "GLOBEX"]
    assert [line.hours for line in report.projects] == [Decimal("250.0")] * 3
    assert [line.amount for line in report.projects] == [
        Decimal("33875.00"),
        Decimal("30000.00"),
        Decimal("24975.00"),
    ]
    assert report.total_amount == Decimal("88850.00")


def test_employee_lines_and_render():
    report = build_report(_store(), PERIOD)
    assert len(report.lines) == 5
    for line in report.lines:
        assert line.hours == Decimal("180.0")
        assert line.billable_hours == Decimal("150.0")
        assert line.capacity == Decimal("160")
        assert line.utilisation == Decimal("112.5")
        assert line.billable_share == Decimal("83.3")
    text = render(report)
    assert "ACME-APP" in text and "INTERNAL" not in text
    assert text.splitlines()[-1].endswith("88850.00")
