from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Protocol

from mailer.config import RelaySettings, from_mapping

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str


class Transport(Protocol):
    def send(self, settings: RelaySettings, sender: str, message: Message) -> None: ...


@dataclass
class DispatchReport:
    sent: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class Dispatcher:
    def __init__(self, settings: RelaySettings, transport: Transport) -> None:
        self._settings = settings
        self._transport = transport

    def send_campaign(self, subject: str, body: str, recipients: Iterable[str]) -> DispatchReport:
        report = DispatchReport()
        seen: set[str] = set()
        for address in recipients:
            normalised = address.strip().lower()
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            message = Message(to=normalised, subject=subject, body=body)
            try:
                self._transport.send(self._settings, self._settings.sender, message)
            except ConnectionError as exc:
                log.warning("delivery to %s failed: %s", normalised, exc)
                report.failed[normalised] = str(exc)
            else:
                report.sent.append(normalised)
        log.info("campaign %r: %d sent, %d failed", subject, len(report.sent), len(report.failed))
        return report


def build_dispatcher(config: Mapping[str, str], transport: Transport) -> Dispatcher:
    return Dispatcher(from_mapping(config), transport)
