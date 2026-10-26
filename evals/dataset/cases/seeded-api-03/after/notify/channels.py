"""Delivery channels for user notifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Message:
    recipient: str
    subject: str
    body: str


class Transport(Protocol):
    async def post(self, endpoint: str, payload: dict[str, str]) -> int:
        """Send `payload` to the provider endpoint and return the HTTP status code."""
        ...


class Channel(Protocol):
    async def send(self, message: Message) -> bool: ...


class EmailChannel:
    endpoint = "/v1/mail/send"

    def __init__(self, transport: Transport, sender: str) -> None:
        self._transport = transport
        self._sender = sender

    async def send(self, message: Message) -> bool:
        status = await self._transport.post(
            self.endpoint,
            {"from": self._sender, "to": message.recipient, "subject": message.subject, "text": message.body},
        )
        return 200 <= status < 300


class SmsChannel:
    endpoint = "/v1/sms"
    max_length = 160

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    async def send(self, message: Message) -> bool:
        text = f"{message.subject}: {message.body}"
        if len(text) > self.max_length:
            text = text[: self.max_length - 1] + "…"
        status = await self._transport.post(self.endpoint, {"to": message.recipient, "text": text})
        return 200 <= status < 300
