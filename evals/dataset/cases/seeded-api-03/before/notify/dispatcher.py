"""Send notifications with retries."""

from __future__ import annotations

from collections.abc import Iterable

from notify.channels import Channel, Message

DEFAULT_ATTEMPTS = 3


def deliver(channel: Channel, message: Message, attempts: int = DEFAULT_ATTEMPTS) -> bool:
    """Send `message`, retrying up to `attempts` times in total. Return whether it was accepted."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for _ in range(attempts):
        if channel.send(message):
            return True
    return False


def broadcast(channel: Channel, recipients: Iterable[str], subject: str, body: str) -> dict[str, bool]:
    """Send the same notification to every recipient; map each recipient to whether it was delivered."""
    return {recipient: deliver(channel, Message(recipient, subject, body)) for recipient in recipients}
