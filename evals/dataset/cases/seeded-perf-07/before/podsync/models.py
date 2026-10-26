from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class PayloadError(ValueError):
    pass


@dataclass(frozen=True)
class Show:
    show_id: str
    title: str
    author: str
    episode_count: int


@dataclass(frozen=True)
class Episode:
    episode_id: str
    show_id: str
    title: str
    published_at: datetime
    duration_seconds: int
    audio_url: str
    explicit: bool = False


def _require(payload: Mapping[str, Any], key: str) -> Any:
    try:
        return payload[key]
    except KeyError:
        raise PayloadError(f"missing field {key!r}") from None


def parse_show(payload: Mapping[str, Any]) -> Show:
    return Show(
        show_id=str(_require(payload, "id")),
        title=str(_require(payload, "title")),
        author=str(payload.get("author") or ""),
        episode_count=int(payload.get("episode_count") or 0),
    )


def parse_episode(show_id: str, payload: Mapping[str, Any]) -> Episode:
    published = datetime.fromisoformat(str(_require(payload, "published_at")))
    audio = _require(payload, "audio")
    return Episode(
        episode_id=str(_require(payload, "id")),
        show_id=show_id,
        title=str(_require(payload, "title")).strip(),
        published_at=published,
        duration_seconds=int(audio.get("duration") or 0),
        audio_url=str(_require(audio, "url")),
        explicit=bool(payload.get("explicit", False)),
    )
