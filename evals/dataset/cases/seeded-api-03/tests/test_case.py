import asyncio

from notify.channels import EmailChannel, Message, SmsChannel
from notify.digest import DigestQueue
from notify.dispatcher import broadcast, deliver


class FakeTransport:
    def __init__(self, failing: set[str] | None = None) -> None:
        self.failing = failing or set()
        self.sent: list[dict[str, str]] = []

    async def post(self, endpoint: str, payload: dict[str, str]) -> int:
        await asyncio.sleep(0)
        if payload["to"] in self.failing:
            return 503
        self.sent.append(payload)
        return 202


def _queue() -> DigestQueue:
    queue = DigestQueue()
    queue.add("ana@example.com", "Ben commented on your post")
    queue.add("ana@example.com", "Your export is ready")
    queue.add("ben@example.com", "New login from a new device")
    return queue


def test_flush_sends_every_digest():
    transport = FakeTransport()
    queue = _queue()
    failed = asyncio.run(queue.flush(EmailChannel(transport, "noreply@example.com")))
    assert failed == []
    assert [p["to"] for p in transport.sent] == ["ana@example.com", "ben@example.com"]
    assert transport.sent[0]["text"] == "- Ben commented on your post\n- Your export is ready"
    assert queue.pending("ana@example.com") == []


def test_undelivered_digest_stays_queued():
    transport = FakeTransport(failing={"ben@example.com"})
    queue = _queue()
    failed = asyncio.run(queue.flush(EmailChannel(transport, "noreply@example.com")))
    assert failed == ["ben@example.com"]
    assert queue.pending("ben@example.com") == ["New login from a new device"]
    assert queue.pending("ana@example.com") == []


def test_deliver_and_broadcast():
    transport = FakeTransport(failing={"+15550002"})
    sms = SmsChannel(transport)
    assert asyncio.run(deliver(sms, Message("+15550001", "Code", "123456")))
    result = asyncio.run(broadcast(sms, ["+15550001", "+15550002", "+15550001"], "Alert", "x" * 300))
    assert result == {"+15550001": True, "+15550002": False}
    assert all(len(p["text"]) == 160 for p in transport.sent[1:])


def test_lines_queued_during_a_flush_are_kept():
    queue = _queue()

    class QueueingTransport(FakeTransport):
        async def post(self, endpoint: str, payload: dict[str, str]) -> int:
            queue.add("ana@example.com", "Late line")
            return await super().post(endpoint, payload)

    transport = QueueingTransport(failing={"ben@example.com"})
    failed = asyncio.run(queue.flush(EmailChannel(transport, "noreply@example.com")))
    assert failed == ["ben@example.com"]
    assert queue.pending("ana@example.com") == ["Late line"] * 4
    assert queue.pending("ben@example.com") == ["New login from a new device"]
