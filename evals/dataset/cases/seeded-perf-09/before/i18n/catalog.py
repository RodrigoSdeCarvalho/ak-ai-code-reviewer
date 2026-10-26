from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class HashClient(Protocol):
    """The subset of a Redis client (created with ``decode_responses=True``) that the catalog uses."""

    def hget(self, name: str, key: str) -> str | None: ...

    def hmget(self, name: str, keys: list[str]) -> list[str | None]: ...

    def hexists(self, name: str, key: str) -> bool: ...

    def hset(self, name: str, key: str, value: str) -> int: ...

    def hdel(self, name: str, *keys: str) -> int: ...


class MessageCatalog(Protocol):
    def get_many(self, locale: str, keys: Sequence[str]) -> dict[str, str]: ...

    def exists(self, locale: str, key: str) -> bool: ...

    def get(self, locale: str, key: str) -> str | None: ...


class RedisCatalog:
    """Translations stored as one Redis hash per locale, edited live by the translation team."""

    def __init__(self, client: HashClient, prefix: str = "i18n") -> None:
        self._client = client
        self._prefix = prefix

    def _hash(self, locale: str) -> str:
        return f"{self._prefix}:{locale}"

    def get_many(self, locale: str, keys: Sequence[str]) -> dict[str, str]:
        if not keys:
            return {}
        values = self._client.hmget(self._hash(locale), list(keys))
        return {key: value for key, value in zip(keys, values) if value is not None}

    def exists(self, locale: str, key: str) -> bool:
        return bool(self._client.hexists(self._hash(locale), key))

    def get(self, locale: str, key: str) -> str | None:
        return self._client.hget(self._hash(locale), key)

    def put(self, locale: str, key: str, text: str) -> None:
        self._client.hset(self._hash(locale), key, text)

    def remove(self, locale: str, key: str) -> bool:
        return self._client.hdel(self._hash(locale), key) > 0
