from typing import Any

import pytest

from helpdesk import client as client_module
from helpdesk.client import ApiError, HelpdeskClient, TransportError
from helpdesk.tickets import add_comment, create_ticket, get_ticket, set_status

TICKET = {"id": 41, "subject": "Printer on fire", "status": "open", "requester": "ana@example.com"}


class ScriptedTransport:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def send(self, method: str, url: str, headers: dict[str, str], json: dict[str, Any] | None):
        self.calls.append((method, url, json))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    recorded: list[float] = []
    monkeypatch.setattr(client_module.time, "sleep", recorded.append)
    return recorded


def _client(transport: ScriptedTransport) -> HelpdeskClient:
    return HelpdeskClient(transport, "https://support.example.com/api/", "tok")


def test_create_ticket_is_never_retried(sleeps: list[float]):
    transport = ScriptedTransport(TransportError("read timed out"), (201, {**TICKET, "id": 42}))
    with pytest.raises(TransportError):
        create_ticket(_client(transport), "Printer on fire", "Smoke from tray 2", "ana@example.com", "urgent")
    assert len(transport.calls) == 1
    assert sleeps == []


def test_create_ticket_sends_only_ticket_fields(sleeps: list[float]):
    transport = ScriptedTransport((201, TICKET))
    ticket = create_ticket(_client(transport), "  Printer on fire ", "Smoke from tray 2", "ana@example.com", "high")
    assert ticket.id == 41
    assert transport.calls == [
        (
            "POST",
            "https://support.example.com/api/tickets",
            {"subject": "Printer on fire", "body": "Smoke from tray 2", "requester": "ana@example.com", "priority": "high"},
        )
    ]
    with pytest.raises(ValueError):
        create_ticket(_client(transport), "Printer", "x", "ana@example.com", "blocker")


def test_reads_are_retried_with_backoff(sleeps: list[float]):
    transport = ScriptedTransport(TransportError("reset"), (503, {"message": "busy"}), (200, TICKET))
    assert get_ticket(_client(transport), 41).subject == "Printer on fire"
    assert len(transport.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_comment_and_status_errors(sleeps: list[float]):
    transport = ScriptedTransport((502, {}), (200, {"id": 9}))
    with pytest.raises(ApiError):
        add_comment(_client(transport), 41, "agent", "On it")
    assert len(transport.calls) == 1
    transport = ScriptedTransport((422, {"message": "bad status transition"}))
    with pytest.raises(ApiError) as info:
        set_status(_client(transport), 41, "solved")
    assert info.value.status == 422
    assert transport.calls[0][2] == {"status": "solved"}
