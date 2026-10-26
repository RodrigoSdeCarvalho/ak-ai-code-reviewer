"""Feature-flag lookups for application code."""

from __future__ import annotations

from flags.backend import FlagBackend
from flags.cache import CachedBackend, CacheStats

DEFAULT_FLAGS: dict[str, bool] = {
    "checkout_v2": False,
    "invoice_pdf_export": True,
    "search_suggestions": True,
    "bulk_refunds": False,
}


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

    def snapshot(self) -> dict[str, bool]:
        """Every known flag with its state: DEFAULT_FLAGS overridden by the backend."""
        return {**DEFAULT_FLAGS, **self._backend.fetch(self._environment)}

    def is_enabled(self, name: str) -> bool:
        """True when the flag is on; flags the backend does not define use DEFAULT_FLAGS, others are off."""
        return self.snapshot().get(name, False)

    def enabled_flags(self) -> list[str]:
        """Names of the flags that are on, sorted."""
        return sorted(name for name, enabled in self.snapshot().items() if enabled)

    def require(self, name: str) -> None:
        """Raise PermissionError unless the flag is on; used to guard unreleased endpoints."""
        if not self.is_enabled(name):
            raise PermissionError(f"feature {name!r} is not enabled in {self._environment}")


def cached(backend: FlagBackend, ttl: float = 30.0, max_stale: float = 300.0) -> CachedBackend:
    """Wrap a backend once at startup and share the result between clients."""
    return CachedBackend(backend, ttl=ttl, max_stale=max_stale)


def client_for(backend: FlagBackend, environment: str) -> FlagClient:
    """Convenience constructor used by the request middleware."""
    return FlagClient(backend, environment.strip().lower())


def describe(client: FlagClient, stats: CacheStats | None = None) -> str:
    """One-line summary for the admin status page."""
    enabled = client.enabled_flags()
    listed = ", ".join(enabled) if enabled else "none"
    line = f"{client.environment}: {len(enabled)} enabled ({listed})"
    if stats is not None:
        line += f"; cache hit rate {stats.hit_rate:.0%}, {stats.stale_served} stale"
    return line
