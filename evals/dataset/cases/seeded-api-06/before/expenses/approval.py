"""Submit expense reports and decide whether they need a manager."""

from __future__ import annotations

from expenses.models import Report, Status
from expenses.policy import check


class InvalidTransition(Exception):
    pass


def submit(report: Report) -> None:
    if report.status is not Status.DRAFT:
        raise InvalidTransition(f"report {report.id} is already {report.status.value}")
    if not report.expenses:
        raise ValueError(f"report {report.id} has no expenses")
    report.status = Status.SUBMITTED


def decide(report: Report) -> Status:
    """Auto-approve a submitted report that is within policy; otherwise send it to a manager."""
    if report.status is not Status.SUBMITTED:
        raise InvalidTransition(f"report {report.id} is {report.status.value}, not submitted")
    if check(report):
        report.status = Status.APPROVED
    else:
        report.status = Status.NEEDS_REVIEW
    return report.status


def approve_manually(report: Report, manager: str) -> None:
    if report.status is not Status.NEEDS_REVIEW:
        raise InvalidTransition(f"report {report.id} is {report.status.value}, not waiting for review")
    if manager == report.employee:
        raise PermissionError("managers cannot approve their own reports")
    report.status = Status.APPROVED
