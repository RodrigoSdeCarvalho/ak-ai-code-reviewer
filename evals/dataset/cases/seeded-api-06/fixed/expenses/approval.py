"""Submit expense reports and decide whether they need a manager."""

from __future__ import annotations

from expenses.models import Report, Status
from expenses.policy import check
from expenses.rates import RateTable


class InvalidTransition(Exception):
    pass


def submit(report: Report) -> None:
    if report.status is not Status.DRAFT:
        raise InvalidTransition(f"report {report.id} is already {report.status.value}")
    if not report.expenses:
        raise ValueError(f"report {report.id} has no expenses")
    report.status = Status.SUBMITTED


def decide(report: Report, rates: RateTable) -> Status:
    """Auto-approve a submitted report that is within policy; otherwise send it to a manager."""
    if report.status is not Status.SUBMITTED:
        raise InvalidTransition(f"report {report.id} is {report.status.value}, not submitted")
    if not check(report, rates):
        report.status = Status.APPROVED
    else:
        report.status = Status.NEEDS_REVIEW
    return report.status


def review_notes(report: Report, rates: RateTable) -> list[str]:
    """Why a report needs a manager, for the approval screen, with the rate date for foreign amounts."""
    notes = check(report, rates)
    if notes and any(expense.currency != "USD" for expense in report.expenses):
        notes.append(f"foreign amounts converted at the {rates.as_of.isoformat()} rates")
    return notes


def approve_manually(report: Report, manager: str) -> None:
    if report.status is not Status.NEEDS_REVIEW:
        raise InvalidTransition(f"report {report.id} is {report.status.value}, not waiting for review")
    if manager == report.employee:
        raise PermissionError("managers cannot approve their own reports")
    report.status = Status.APPROVED
