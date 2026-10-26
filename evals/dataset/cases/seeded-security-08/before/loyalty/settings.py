from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


class SettingsError(ValueError):
    pass


def _split_list(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _int_setting(raw: Mapping[str, str], name: str, default: int, minimum: int = 0) -> int:
    value = raw.get(name)
    if value is None or not value.strip():
        return default
    try:
        number = int(value)
    except ValueError:
        raise SettingsError(f"{name} must be an integer, got {value!r}") from None
    if number < minimum:
        raise SettingsError(f"{name} must be at least {minimum}")
    return number


@dataclass(frozen=True)
class Settings:
    program_name: str = "Rewards"
    allowed_origins: tuple[str, ...] = ()
    cors_max_age: int = 600

    @classmethod
    def from_mapping(cls, raw: Mapping[str, str]) -> Settings:
        origins = tuple(origin.rstrip("/").lower() for origin in _split_list(raw.get("LOYALTY_ALLOWED_ORIGINS", "")))
        for origin in origins:
            if not origin.startswith("https://"):
                raise SettingsError(f"allowed origin {origin!r} must use https")
        return cls(
            program_name=raw.get("LOYALTY_PROGRAM_NAME", "Rewards").strip() or "Rewards",
            allowed_origins=origins,
            cors_max_age=_int_setting(raw, "LOYALTY_CORS_MAX_AGE", 600),
        )
