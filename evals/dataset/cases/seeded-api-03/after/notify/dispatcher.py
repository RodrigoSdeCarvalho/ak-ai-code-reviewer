"""Send notifications with retries."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable

from notify.channels import Channel, Message

DEFAULT_ATTEMPTS = 3
MAX_CONCURRENT_SENDS = 10


async def deliver(channel: Channel, message: Message, attempts: int = DEFAULT_ATTEMPTS) -> bool:
    """Send `message`, retrying up to `attempts` times in total. Return whether it was accepted."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for _ in range(attempts):
        if await channel.send(message):
            return True
    return False


async def broadcast(channel: Channel, recipients: Iterable[str], subject: str, body: str) -> dict[str, bool]:
    """Send the same notification to every recipient; map each recipient to whether it was delivered.

    At most MAX_CONCURRENT_SENDS messages are in flight at once.
    """
    limit = asyncio.Semaphore(MAX_CONCURRENT_SENDS)

    async def send_one(recipient: str) -> bool:
        async with limit:
            return await deliver(channel, Message(recipient, subject, body))

    targets = list(dict.fromkeys(recipients))
    results = await asyncio.gather(*(send_one(recipient) for recipient in targets))
    return dict(zip(targets, results, strict=True))
