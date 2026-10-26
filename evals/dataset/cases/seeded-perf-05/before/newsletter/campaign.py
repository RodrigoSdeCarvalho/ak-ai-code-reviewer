from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from urllib.parse import urlencode

from newsletter.mailer import Mailer, Message


@dataclass(frozen=True)
class Subscriber:
    email: str
    name: str
    lists: frozenset[str] = field(default_factory=frozenset)
    confirmed: bool = True
    unsubscribed: bool = False


@dataclass(frozen=True)
class Campaign:
    slug: str
    list_name: str
    sender: str
    subject: str
    body_template: str
    unsubscribe_base: str


def eligible(subscribers: Iterable[Subscriber], campaign: Campaign) -> Iterator[Subscriber]:
    seen: set[str] = set()
    for subscriber in subscribers:
        address = subscriber.email.strip().lower()
        if address in seen:
            continue
        if not subscriber.confirmed or subscriber.unsubscribed:
            continue
        if campaign.list_name not in subscriber.lists:
            continue
        seen.add(address)
        yield subscriber


def render(campaign: Campaign, subscriber: Subscriber) -> Message:
    first_name = subscriber.name.split(" ")[0] if subscriber.name else "there"
    query = urlencode({"list": campaign.list_name, "email": subscriber.email})
    unsubscribe = f"{campaign.unsubscribe_base}?{query}"
    body = campaign.body_template.format(first_name=first_name)
    return Message(
        sender=campaign.sender,
        to=subscriber.email,
        subject=campaign.subject,
        body=f"{body}\n\n--\nUnsubscribe: {unsubscribe}\n",
        headers={
            "List-Unsubscribe": f"<{unsubscribe}>",
            "X-Campaign": campaign.slug,
        },
    )


def send_test(mailer: Mailer, campaign: Campaign, address: str) -> None:
    preview = Subscriber(email=address, name="Test Recipient", lists=frozenset({campaign.list_name}))
    message = render(campaign, preview)
    mailer.send(Message(message.sender, message.to, f"[TEST] {message.subject}", message.body, message.headers))
