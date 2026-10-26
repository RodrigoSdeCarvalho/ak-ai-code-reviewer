from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

FOOTER = (
    "\n\n--\nRiverside Allotment Association\n"
    "You receive this email because you are a member or on the plot waiting list."
)


class MailerError(Exception):
    pass


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    body: str


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


def compose(to: str, subject: str, body: str) -> Email:
    if "@" not in to:
        raise MailerError(f"not an email address: {to!r}")
    if not subject.strip():
        raise MailerError("subject must not be empty")
    return Email(to, subject.strip(), body.rstrip() + FOOTER)


class Outbox:
    """Mailer that keeps messages in memory; the nightly relay job delivers them."""

    def __init__(self) -> None:
        self.messages: list[Email] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.messages.append(compose(to, subject, body))

    def for_recipient(self, to: str) -> list[Email]:
        return [m for m in self.messages if m.to == to]

    def clear(self) -> None:
        self.messages.clear()
