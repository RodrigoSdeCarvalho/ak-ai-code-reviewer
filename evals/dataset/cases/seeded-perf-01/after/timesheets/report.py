"""Utilisation and billing report for a reporting period."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from timesheets.models import Employee, Period, Project
from timesheets.repository import TimesheetStore

PERCENT = Decimal("0.1")
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class EmployeeLine:
    employee: Employee
    hours: Decimal
    billable_hours: Decimal
    capacity: Decimal

    @property
    def utilisation(self) -> Decimal:
        if not self.capacity:
            return Decimal(0)
        return (self.hours / self.capacity * 100).quantize(PERCENT, ROUND_HALF_UP)

    @property
    def billable_share(self) -> Decimal:
        if not self.hours:
            return Decimal(0)
        return (self.billable_hours / self.hours * 100).quantize(PERCENT, ROUND_HALF_UP)


@dataclass(frozen=True)
class ProjectLine:
    project: Project
    hours: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Report:
    period: Period
    lines: list[EmployeeLine]
    projects: list[ProjectLine]

    @property
    def total_hours(self) -> Decimal:
        return sum((line.hours for line in self.lines), Decimal(0))

    @property
    def total_amount(self) -> Decimal:
        return sum((line.amount for line in self.projects), Decimal(0))


def build_report(store: TimesheetStore, period: Period) -> Report:
    entries = store.entries_between(period.start, period.end)
    hours_by_employee: dict[int, Decimal] = defaultdict(Decimal)
    billable_by_employee: dict[int, Decimal] = defaultdict(Decimal)
    hours_by_project: dict[int, Decimal] = defaultdict(Decimal)
    projects: dict[int, Project] = {}
    for entry in entries:
        hours_by_employee[entry.employee_id] += entry.hours
        hours_by_project[entry.project_id] += entry.hours
        project = store.project(entry.project_id)
        projects[project.id] = project
        if project.billable:
            billable_by_employee[entry.employee_id] += entry.hours

    employees = store.employees(hours_by_employee)
    lines = [
        EmployeeLine(
            employee=employees[employee_id],
            hours=hours,
            billable_hours=billable_by_employee[employee_id],
            capacity=employees[employee_id].weekly_capacity * period.weeks,
        )
        for employee_id, hours in hours_by_employee.items()
    ]
    lines.sort(key=lambda line: (-line.utilisation, line.employee.name))
    project_lines = [
        ProjectLine(
            project=projects[project_id],
            hours=hours,
            amount=(hours * projects[project_id].hourly_rate).quantize(CENTS, ROUND_HALF_UP),
        )
        for project_id, hours in hours_by_project.items()
        if projects[project_id].billable
    ]
    project_lines.sort(key=lambda line: (-line.amount, line.project.code))
    return Report(period=period, lines=lines, projects=project_lines)


def render(report: Report) -> str:
    header = f"Utilisation {report.period.start:%Y-%m-%d} to {report.period.end:%Y-%m-%d}"
    rows = [header, f"{'Employee':<20}{'Hours':>8}{'Util %':>8}{'Bill %':>8}"]
    for line in report.lines:
        rows.append(
            f"{line.employee.name:<20}{line.hours:>8}{line.utilisation:>8}{line.billable_share:>8}"
        )
    rows.append(f"{'Total':<20}{report.total_hours:>8}")
    rows.append("")
    rows.append(f"{'Project':<20}{'Hours':>8}{'Amount':>12}")
    for project_line in report.projects:
        rows.append(
            f"{project_line.project.code:<20}{project_line.hours:>8}{project_line.amount:>12}"
        )
    rows.append(f"{'Total':<20}{'':>8}{report.total_amount:>12}")
    return "\n".join(rows)
