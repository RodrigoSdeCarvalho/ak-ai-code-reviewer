"""Gateway hook that applies the configured limiter before a request is routed."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ratelimit.limiter import Clock, FixedWindowLimiter, Limiter


@dataclass
class Request:
    path: str
    headers: dict[str, str] = field(default_factory=dict)
    client_ip: str = "0.0.0.0"


@dataclass
class Response:
    status: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)


Handler = Callable[[Request], Response]

EXPENSIVE_PREFIXES = ("/v1/search", "/v1/export")


def client_key(request: Request) -> str:
    """API key when present, otherwise the caller's IP address."""
    api_key = request.headers.get("x-api-key", "").strip()
    return f"key:{api_key}" if api_key else f"ip:{request.client_ip}"


def request_cost(request: Request) -> int:
    return 5 if request.path.startswith(EXPENSIVE_PREFIXES) else 1


def build_limiter(config: dict[str, Any], clock: Clock) -> Limiter:
    return FixedWindowLimiter(int(config["limit"]), float(config["window_seconds"]), clock)


def rate_limited(handler: Handler, limiter: Limiter) -> Handler:
    """Wrap a handler so over-limit requests get 429 with a Retry-After header."""

    def wrapper(request: Request) -> Response:
        decision = limiter.check(client_key(request), request_cost(request))
        if not decision.allowed:
            retry = max(1, math.ceil(decision.retry_after))
            return Response(429, {"error": "rate limit exceeded"}, {"Retry-After": str(retry)})
        response = handler(request)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        return response

    return wrapper
