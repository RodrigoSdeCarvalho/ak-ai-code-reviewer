"""Provider-neutral LLM call contract. Everything that talks to a model goes through `LLMClient`."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol

from pydantic import BaseModel, Field

from aireview.models import Usage


class LLMRequest(BaseModel):
    """One structured-output call.

    `role` separates reviewer and judge cassettes; `sample` lets k independent samples of the same
    prompt be stored side by side (there is no temperature/seed control on current models).
    """

    role: str  # "reviewer" | "judge"
    model: str
    system: str
    user: str
    output_schema: dict[str, Any]  # JSON schema of the expected object
    max_tokens: int = 16000
    effort: str | None = None  # output_config.effort; None = model default
    sample: int = 0
    prompt_version: str = "unversioned"

    def key(self) -> str:
        """Content address: any change to model, prompt, schema, effort or sample index is a new key."""
        payload = json.dumps(
            {
                "role": self.role,
                "model": self.model,
                "system": self.system,
                "user": self.user,
                "schema": self.output_schema,
                "max_tokens": self.max_tokens,
                "effort": self.effort,
                "sample": self.sample,
                "prompt_version": self.prompt_version,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class LLMResponse(BaseModel):
    """What came back. `parsed` is the JSON object when the call produced one."""

    parsed: dict[str, Any] | None = None
    raw_text: str | None = None
    stop_reason: str | None = None
    served_model: str | None = None
    usage: Usage = Field(default_factory=Usage)
    error: str | None = None  # set when no usable output was produced (after retries)
    error_class: str | None = None  # api_error | schema_error | refused | truncated | timeout
    request_id: str | None = None
    from_cache: bool = False
    batch: bool = False
    attempts: int = 1  # API attempts made, including the final one (retries = attempts - 1)


# Error classes of a response built from a real model message: the model's own outcome, recorded and
# replayed like a success. Every other class (api_error, timeout, cassette_missing) is a transport failure.
MODEL_OUTCOME_CLASSES = frozenset({"truncated", "refused", "schema_error", "model_mismatch"})


def is_model_outcome(response: LLMResponse) -> bool:
    """True for a success or a model-produced failure (stored in cassettes); False for transport failures."""
    return response.error is None or response.error_class in MODEL_OUTCOME_CLASSES


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResponse: ...

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        """Default implementations loop over `complete`; the batch client overrides this."""
        ...
