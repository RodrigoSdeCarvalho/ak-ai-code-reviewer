"""Ticket operations used by the support portal and the inbound-email worker."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helpdesk.client import HelpdeskClient


@dataclass(frozen=True)
class Ticket:
    id: int
    subject: str
    status: str
    requester: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Ticket:
        return cls(
            id=int(payload["id"]),
            subject=str(payload["subject"]),
            status=str(payload["status"]),
            requester=str(payload["requester"]),
        )


def create_ticket(client: HelpdeskClient, subject: str, body: str, requester: str) -> Ticket:
    if not subject.strip():
        raise ValueError("subject is required")
    payload = client.request(
        "POST",
        "/tickets",
        subject=subject.strip(),
        body=body,
        requester=requester,
        attempts=1,
    )
    return Ticket.from_payload(payload)


def add_comment(client: HelpdeskClient, ticket_id: int, author: str, text: str, public: bool = True) -> int:
    payload = client.request(
        "POST", f"/tickets/{ticket_id}/comments", attempts=1, author=author, text=text, public=public
    )
    return int(payload["id"])


def get_ticket(client: HelpdeskClient, ticket_id: int) -> Ticket:
    return Ticket.from_payload(client.request("GET", f"/tickets/{ticket_id}"))


def set_status(client: HelpdeskClient, ticket_id: int, status: str) -> Ticket:
    if status not in ("open", "pending", "solved", "closed"):
        raise ValueError(f"unknown status {status!r}")
    return Ticket.from_payload(client.request("PUT", f"/tickets/{ticket_id}", status=status))
