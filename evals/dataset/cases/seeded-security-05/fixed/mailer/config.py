from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_PORT = 587
ENV_PREFIX = "MAILER_RELAY_"

log = logging.getLogger(__name__)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RelaySettings:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = True
    sender: str = "newsletter@localhost"


def _parse_port(raw: str) -> int:
    try:
        port = int(raw)
    except ValueError as exc:
        raise ConfigError(f"relay port must be a number, got {raw!r}") from exc
    if not 0 < port < 65536:
        raise ConfigError(f"relay port out of range: {port}")
    return port


def _parse_bool(raw: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"expected a boolean, got {raw!r}")


def from_mapping(values: Mapping[str, str]) -> RelaySettings:
    missing = [key for key in ("host", "username", "password") if not values.get(key)]
    if missing:
        raise ConfigError(f"missing relay settings: {', '.join(missing)}")
    return RelaySettings(
        host=values["host"],
        port=_parse_port(values.get("port", str(DEFAULT_PORT))),
        username=values["username"],
        password=values["password"],
        use_tls=_parse_bool(values.get("use_tls", "true")),
        sender=values.get("sender", "newsletter@localhost"),
    )


def from_env(environ: Mapping[str, str], defaults: Mapping[str, str] | None = None) -> RelaySettings:
    values = dict(defaults or {})
    for name, raw in environ.items():
        if name.startswith(ENV_PREFIX) and raw.strip():
            values[name[len(ENV_PREFIX) :].lower()] = raw.strip()
    settings = from_mapping(values)
    log.info(
        "mail relay configured: %s@%s:%d tls=%s sender=%s",
        settings.username,
        settings.host,
        settings.port,
        settings.use_tls,
        settings.sender,
    )
    return settings
