from __future__ import annotations

from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

from loyalty.settings import Settings

ALLOWED_METHODS = ("GET", "POST")
ALLOWED_HEADERS = ("content-type", "x-request-id")


class CorsPolicy:
    """Decides which browser origins may call the API with the member's session cookie.

    Origins are allowed either exactly (``allowed_origins``) or because they are served over https
    from a partner's domain (``partner_domains``), which covers every storefront a partner runs on
    its own subdomains without listing each one.
    """

    def __init__(self, exact_origins: Iterable[str], partner_domains: Iterable[str], max_age: int) -> None:
        self._exact = frozenset(origin.rstrip("/").lower() for origin in exact_origins)
        self._partner_domains = tuple(domain.lower() for domain in partner_domains)
        self._max_age = max_age

    @classmethod
    def from_settings(cls, settings: Settings) -> CorsPolicy:
        return cls(settings.allowed_origins, settings.partner_domains, settings.cors_max_age)

    def is_allowed(self, origin: str | None) -> bool:
        if not origin:
            return False
        normalised = origin.rstrip("/").lower()
        if normalised in self._exact:
            return True
        try:
            parts = urlsplit(normalised)
        except ValueError:
            return False
        if parts.scheme != "https" or not parts.hostname or parts.path or parts.query:
            return False
        host = parts.hostname
        return any(host == domain or host.endswith("." + domain) for domain in self._partner_domains)

    def response_headers(self, origin: str | None) -> dict[str, str]:
        headers = {"Vary": "Origin"}
        if self.is_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        return headers

    def preflight_headers(self, origin: str | None, request_headers: Mapping[str, str]) -> dict[str, str]:
        headers = {"Vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers"}
        if not self.is_allowed(origin):
            return headers
        method = request_headers.get("access-control-request-method", "").upper()
        if method not in ALLOWED_METHODS:
            return headers
        requested = _header_list(request_headers.get("access-control-request-headers", ""))
        if any(name not in ALLOWED_HEADERS for name in requested):
            return headers
        headers.update(
            {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": ", ".join(ALLOWED_METHODS),
                "Access-Control-Allow-Headers": ", ".join(ALLOWED_HEADERS),
                "Access-Control-Max-Age": str(self._max_age),
            }
        )
        return headers


def _header_list(raw: str) -> list[str]:
    return [name.strip().lower() for name in raw.split(",") if name.strip()]
