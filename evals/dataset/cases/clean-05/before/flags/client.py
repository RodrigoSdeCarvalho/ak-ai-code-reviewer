"""Feature-flag lookups for application code."""

from __future__ import annotations

from flags.backend import FlagBackend


class FlagClient:
    """Answers whether a flag is on in one environment."""

    def __init__(self, backend: FlagBackend, environment: str) -> None:
        if not environment:
            raise ValueError("environment is required")
        self._backend = backend
        self._environment = environment

    @property
    def environment(self) -> str:
        return self._environment

    def is_enabled(self, name: str) -> bool:
        """True when the flag is switched on; unknown flags are off."""
        return self._backend.fetch(self._environment).get(name, False)

    def enabled_flags(self) -> list[str]:
        """Names of the flags that are on, sorted."""
        flags = self._backend.fetch(self._environment)
        return sorted(name for name, enabled in flags.items() if enabled)

    def require(self, name: str) -> None:
        """Raise PermissionError unless the flag is on; used to guard unreleased endpoints."""
        if not self.is_enabled(name):
            raise PermissionError(f"feature {name!r} is not enabled in {self._environment}")


def client_for(backend: FlagBackend, environment: str) -> FlagClient:
    """Convenience constructor used by the request middleware."""
    return FlagClient(backend, environment.strip().lower())


def describe(client: FlagClient) -> str:
    """One-line summary for the admin status page."""
    enabled = client.enabled_flags()
    listed = ", ".join(enabled) if enabled else "none"
    return f"{client.environment}: {len(enabled)} enabled ({listed})"
