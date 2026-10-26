"""Where feature-flag definitions are stored."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class BackendUnavailable(RuntimeError):
    """The flag store could not be read."""


class FlagBackend(Protocol):
    def fetch(self, environment: str) -> dict[str, bool]:
        """All flags of `environment` with their on/off state."""
        ...


class InMemoryBackend:
    """Flags held in a dict; used by tests and local development."""

    def __init__(self, flags: dict[str, dict[str, bool]] | None = None) -> None:
        self._flags = {env: dict(values) for env, values in (flags or {}).items()}
        self.fetches = 0

    def set(self, environment: str, name: str, enabled: bool) -> None:
        self._flags.setdefault(environment, {})[name] = enabled

    def fetch(self, environment: str) -> dict[str, bool]:
        self.fetches += 1
        return dict(self._flags.get(environment, {}))


class JsonFileBackend:
    """Flags in a JSON document of the form {"<environment>": {"<flag>": true}}."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def fetch(self, environment: str) -> dict[str, bool]:
        try:
            document = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BackendUnavailable(f"cannot read {self._path}: {exc}") from exc
        values = document.get(environment, {})
        return {str(name): bool(enabled) for name, enabled in values.items()}
