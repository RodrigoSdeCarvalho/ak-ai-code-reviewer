"""Utilisation report for a reporting period."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from timesheets.models import Employee, Period
from timesheets.repository import TimesheetStore

PERCENT = Decimal("0.1")


@dataclass(frozen=True)
class EmployeeLine:
    employee: Employee
    hours: Decimal
    capacity: Decimal

    @property
    def utilisation(self) -> Decimal:
        if not self.capacity:
            return Decimal(0)
        return (self.hours / self.capacity * 100).quantize(PERCENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class Report:
    period: Period
    lines: list[EmployeeLine]

    @property
    def total_hours(self) -> Decimal:
        return sum((line.hours for line in self.lines), Decimal(0))


def build_report(store: TimesheetStore, period: Period) -> Report:
    entries = store.entries_between(period.start, period.end)
    hours_by_employee: dict[int, Decimal] = defaultdict(Decimal)
    for entry in entries:
        hours_by_employee[entry.employee_id] += entry.hours

    employees = store.employees(hours_by_employee)
    lines = [
        EmployeeLine(
            employee=employees[employee_id],
            hours=hours,
            capacity=employees[employee_id].weekly_capacity * period.weeks,
        )
        for employee_id, hours in hours_by_employee.items()
    ]
    lines.sort(key=lambda line: (-line.utilisation, line.employee.name))
    return Report(period=period, lines=lines)


def render(report: Report) -> str:
    header = f"Utilisation {report.period.start:%Y-%m-%d} to {report.period.end:%Y-%m-%d}"
    rows = [header, f"{'Employee':<20}{'Hours':>8}{'Util %':>8}"]
    for line in report.lines:
        rows.append(f"{line.employee.name:<20}{line.hours:>8}{line.utilisation:>8}")
    rows.append(f"{'Total':<20}{report.total_hours:>8}")
    return "\n".join(rows)
