"""Runtime settings: a dependency-free .env loader, model defaults and the price table."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_REVIEWER_MODEL = "claude-sonnet-5-5"
DEFAULT_JUDGE_MODEL = "claude-haiku-5-5"
CROSS_JUDGE_MODEL = "claude-opus-5-5"

# USD per million tokens (Anthropic first-party list prices, checked 2026-10-23).
# cache_write = 1.25x input (5-minute TTL), cache_read = 0.1x input unless listed otherwise.
PRICES: dict[str, dict[str, float]] = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50, "cache_read": 0.01, "cache_write": 0.125},
}
BATCH_DISCOUNT = 0.5


def repo_root() -> Path:
    """The deliverable repo root (the directory holding pyproject.toml)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def load_dotenv(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from .env into os.environ. Variables already set win."""
    path = path or repo_root() / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int = 0,
    cache_write: int = 0,
    batch: bool = False,
) -> float:
    """Cost from recorded token counts. Unknown models raise: a silent 0 would hide spend."""
    if model not in PRICES:
        raise KeyError(f"no price for model {model!r}; add it to aireview.settings.PRICES")
    p = PRICES[model]
    total = (
        input_tokens * p["input"]
        + output_tokens * p["output"]
        + cache_read * p["cache_read"]
        + cache_write * p["cache_write"]
    ) / 1_000_000
    return total * (BATCH_DISCOUNT if batch else 1.0)
