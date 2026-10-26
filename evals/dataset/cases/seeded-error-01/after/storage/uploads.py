"""Attachment uploads: store the bytes, then record them in the attachment index."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from storage.blobs import BlobStore

DEFAULT_MAX_BYTES = 10 * 1024 * 1024


class AttachmentNotFound(KeyError):
    """No attachment has the requested id."""


@dataclass(frozen=True)
class Attachment:
    id: int
    filename: str
    blob_key: str
    size: int
    uploaded_at: datetime


class AttachmentService:
    def __init__(self, blobs: BlobStore, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self._blobs = blobs
        self._max_bytes = max_bytes
        self._index: dict[int, Attachment] = {}
        self._next_id = 1

    def upload(self, filename: str, data: bytes, now: datetime) -> Attachment:
        if not data:
            raise ValueError("empty upload")
        if len(data) > self._max_bytes:
            raise ValueError(f"upload exceeds {self._max_bytes} bytes")
        info = self._blobs.put(data)
        attachment = Attachment(self._next_id, filename, info.key, info.size, now)
        self._index[attachment.id] = attachment
        self._next_id += 1
        return attachment

    def download(self, attachment_id: int) -> tuple[Attachment, bytes]:
        attachment = self._get(attachment_id)
        return attachment, self._blobs.get(attachment.blob_key)

    def remove(self, attachment_id: int) -> None:
        """Remove an attachment, deleting its blob once no other attachment shares it."""
        attachment = self._get(attachment_id)
        del self._index[attachment_id]
        if not any(other.blob_key == attachment.blob_key for other in self._index.values()):
            self._blobs.delete(attachment.blob_key)

    def _get(self, attachment_id: int) -> Attachment:
        try:
            return self._index[attachment_id]
        except KeyError:
            raise AttachmentNotFound(attachment_id) from None
