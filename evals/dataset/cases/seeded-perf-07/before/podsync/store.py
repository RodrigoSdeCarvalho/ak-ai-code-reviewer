from __future__ import annotations

import sqlite3
from datetime import datetime

from podsync.models import Episode

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    episode_id TEXT PRIMARY KEY,
    show_id TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT NOT NULL,
    duration_seconds INTEGER NOT NULL,
    audio_url TEXT NOT NULL,
    explicit INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS episodes_by_show ON episodes (show_id, published_at);
"""


class CatalogueStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(SCHEMA)

    def upsert_episode(self, episode: Episode) -> bool:
        exists = self._conn.execute(
            "SELECT 1 FROM episodes WHERE episode_id = ?", (episode.episode_id,)
        ).fetchone()
        with self._conn:
            self._conn.execute(
                "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (episode_id) DO UPDATE SET title = excluded.title, "
                "published_at = excluded.published_at, duration_seconds = excluded.duration_seconds, "
                "audio_url = excluded.audio_url, explicit = excluded.explicit",
                (
                    episode.episode_id,
                    episode.show_id,
                    episode.title,
                    episode.published_at.isoformat(),
                    episode.duration_seconds,
                    episode.audio_url,
                    int(episode.explicit),
                ),
            )
        return exists is None

    def episode_ids(self, show_id: str) -> list[str]:
        rows = self._conn.execute(
            "SELECT episode_id FROM episodes WHERE show_id = ? ORDER BY published_at, episode_id",
            (show_id,),
        ).fetchall()
        return [row[0] for row in rows]

    def count(self, show_id: str) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM episodes WHERE show_id = ?", (show_id,)).fetchone()[0]

    def latest_published(self, show_id: str) -> datetime | None:
        row = self._conn.execute(
            "SELECT MAX(published_at) FROM episodes WHERE show_id = ?", (show_id,)
        ).fetchone()
        return datetime.fromisoformat(row[0]) if row[0] else None
