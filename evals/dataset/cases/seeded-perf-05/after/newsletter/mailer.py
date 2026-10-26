from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol


class RecipientRefused(Exception):
    def __init__(self, address: str, reason: str) -> None:
        super().__init__(f"{address}: {reason}")
        self.address = address
        self.reason = reason


@dataclass(frozen=True)
class Message:
    sender: str
    to: str
    subject: str
    body: str
    headers: dict[str, str] = field(default_factory=dict)


class Transport(Protocol):
    def login(self, username: str, password: str) -> None: ...

    def deliver(self, message: Message) -> None: ...

    def quit(self) -> None: ...


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int = 587
    username: str = ""
    password: str = ""


TransportFactory = Callable[[str, int], Transport]


class Mailer:
    def __init__(self, settings: SmtpSettings, factory: TransportFactory) -> None:
        self._settings = settings
        self._factory = factory

    @contextmanager
    def session(self) -> Iterator[Transport]:
        transport = self._factory(self._settings.host, self._settings.port)
        try:
            if self._settings.username:
                transport.login(self._settings.username, self._settings.password)
            yield transport
        finally:
            transport.quit()

    def send(self, message: Message) -> None:
        with self.session() as transport:
            transport.deliver(message)
