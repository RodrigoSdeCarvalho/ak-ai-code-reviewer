"""HTTP-style handlers for the attachment endpoints, independent of the web framework."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from attachments.store import AttachmentStore, InvalidName, NotFound, TooLarge, UnsupportedType, content_type_for


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


def _json(status: int, payload: dict[str, object]) -> Response:
    return Response(status, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})


def upload(store: AttachmentStore, filename: str, data: bytes) -> Response:
    """POST /attachments: store the file and return its name."""
    try:
        stored = store.save(data, filename)
    except TooLarge as exc:
        return _json(413, {"error": str(exc)})
    except UnsupportedType as exc:
        return _json(415, {"error": str(exc)})
    return _json(201, {"name": stored.name, "size": stored.size, "content_type": stored.content_type})


def download(store: AttachmentStore, name: str) -> Response:
    """GET /attachments/<name>: the file bytes."""
    try:
        data = store.read(name)
    except InvalidName:
        return _json(400, {"error": "invalid attachment name"})
    except NotFound:
        return _json(404, {"error": "no such attachment"})
    return Response(200, data, {"Content-Type": content_type_for(name)})
