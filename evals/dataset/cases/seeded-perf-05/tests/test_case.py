from newsletter.campaign import Campaign, Subscriber, send_campaign, send_test
from newsletter.mailer import Mailer, Message, RecipientRefused, SmtpSettings


class FakeServer:
    def __init__(self, rejects: dict[str, str] | None = None) -> None:
        self.rejects = rejects or {}
        self.connections = 0
        self.logins = 0
        self.open = 0
        self.delivered: list[Message] = []

    def connect(self, host: str, port: int) -> "FakeTransport":
        self.connections += 1
        self.open += 1
        return FakeTransport(self)


class FakeTransport:
    def __init__(self, server: FakeServer) -> None:
        self.server = server

    def login(self, username: str, password: str) -> None:
        self.server.logins += 1

    def deliver(self, message: Message) -> None:
        if message.to in self.server.rejects:
            raise RecipientRefused(message.to, self.server.rejects[message.to])
        self.server.delivered.append(message)

    def quit(self) -> None:
        self.server.open -= 1


CAMPAIGN = Campaign(
    slug="spring-26",
    list_name="weekly",
    sender="news@example.org",
    subject="Spring update",
    body_template="Hi {first_name}, here is what is new.",
    unsubscribe_base="https://example.org/unsubscribe",
)


def _mailer(server: FakeServer) -> Mailer:
    return Mailer(SmtpSettings("smtp.example.org", username="news", password="pw"), server.connect)


def _subscribers(n: int) -> list[Subscriber]:
    return [Subscriber(f"reader{i}@example.com", f"Reader {i}", frozenset({"weekly"})) for i in range(n)]


def test_campaign_reuses_one_smtp_connection():
    server = FakeServer()
    report = send_campaign(_mailer(server), CAMPAIGN, _subscribers(200))
    assert len(report.sent) == 200
    assert server.connections == 1
    assert server.logins == 1
    assert server.open == 0


def test_refused_recipients_are_reported_and_others_still_sent():
    server = FakeServer(rejects={"reader1@example.com": "mailbox full"})
    subscribers = _subscribers(3) + [
        Subscriber("READER0@example.com ", "Dup", frozenset({"weekly"})),
        Subscriber("other@example.com", "Other", frozenset({"monthly"})),
        Subscriber("pending@example.com", "Pending", frozenset({"weekly"}), confirmed=False),
        Subscriber("gone@example.com", "Gone", frozenset({"weekly"}), unsubscribed=True),
    ]
    report = send_campaign(_mailer(server), CAMPAIGN, subscribers)
    assert report.sent == ["reader0@example.com", "reader2@example.com"]
    assert report.refused == {"reader1@example.com": "mailbox full"}
    assert report.attempted == 3
    assert server.open == 0
    first = server.delivered[0]
    assert first.body.startswith("Hi Reader, here is what is new.")
    assert first.headers["List-Unsubscribe"] == (
        "<https://example.org/unsubscribe?list=weekly&email=reader0%40example.com>"
    )
    assert first.headers["X-Campaign"] == "spring-26"


def test_test_send_still_goes_out_alone():
    server = FakeServer()
    send_test(_mailer(server), CAMPAIGN, "editor@example.org")
    assert server.connections == 1
    assert [m.subject for m in server.delivered] == ["[TEST] Spring update"]
