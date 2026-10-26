"""Batch low-priority notifications into one digest per recipient."""

from __future__ import annotations

from collections import defaultdict

from notify.channels import Channel, Message
from notify.dispatcher import deliver

DIGEST_SUBJECT = "Your daily digest"
MAX_LINES = 50


def render(lines: list[str]) -> str:
    """Render digest lines as a bulleted body, summarising any lines past MAX_LINES."""
    shown = [f"- {line}" for line in lines[:MAX_LINES]]
    hidden = len(lines) - MAX_LINES
    if hidden > 0:
        shown.append(f"... and {hidden} more")
    return "\n".join(shown)


class DigestQueue:
    def __init__(self) -> None:
        self._pending: dict[str, list[str]] = defaultdict(list)

    def add(self, recipient: str, line: str) -> None:
        self._pending[recipient].append(line)

    def pending(self, recipient: str) -> list[str]:
        return list(self._pending.get(recipient, []))

    async def flush(self, channel: Channel, subject: str = DIGEST_SUBJECT) -> list[str]:
        """Send one digest per recipient and return the recipients whose digest was not delivered.

        Each digest is retried like any other notification. Delivered lines are removed from the
        queue, keeping any queued while the digest was being sent; undelivered ones stay queued for
        the next flush.
        """
        failed: list[str] = []
        for recipient in sorted(self._pending):
            lines = self._pending[recipient]
            sent = len(lines)
            message = Message(recipient, subject, render(lines))
            if deliver(channel, message):
                del lines[:sent]
                if not lines:
                    del self._pending[recipient]
            else:
                failed.append(recipient)
        return failed
