"""Content-addressed cassettes and the two explicit modes.

`replay` never touches the network: a missing cassette is an error row, not a live call.
`record` calls the model and stores every model outcome (success, truncation, refusal, schema error,
served-model mismatch) so replay reproduces it; transport failures (api_error, timeout) are not stored.
Cassettes are write-once: record reads an existing cassette only with `resume=True` and otherwise refuses
to overwrite it (`CassetteConflict`), so re-recording can never change what an earlier run replays.
Independent repeat runs use distinct sample indices (`--sample-offset`).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aireview.llm.base import LLMClient, LLMRequest, LLMResponse, is_model_outcome
from aireview.settings import repo_root


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CassetteStore:
    """One JSON file per request at `<root>/<role>/<model>/<key>.json`."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else repo_root() / "evals" / "cassettes"

    def path_for(self, request: LLMRequest) -> Path:
        return self.root / request.role / request.model / f"{request.key()}.json"

    def exists(self, request: LLMRequest) -> bool:
        return self.path_for(request).is_file()

    def get(self, request: LLMRequest) -> LLMResponse | None:
        path = self.path_for(request)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        stored_key = data["request_meta"]["key"]
        if stored_key != request.key():
            raise ValueError(f"cassette {path} holds key {stored_key}, expected {request.key()}")
        return LLMResponse.model_validate(data["response"]).model_copy(update={"from_cache": True})

    def put(self, request: LLMRequest, response: LLMResponse) -> None:
        record = {
            "request_meta": _request_meta(request),
            "response": response.model_copy(update={"from_cache": False}).model_dump(mode="json"),
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        _atomic_write(self.path_for(request), json.dumps(record, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def _request_meta(request: LLMRequest) -> dict[str, Any]:
    return {
        "role": request.role,
        "model": request.model,
        "prompt_version": request.prompt_version,
        "sample": request.sample,
        "effort": request.effort,
        "max_tokens": request.max_tokens,
        "key": request.key(),
        "system_sha256": _sha256(request.system),
        "user_sha256": _sha256(request.user),
        "user_chars": len(request.user),
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.stem}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class CassetteConflict(RuntimeError):
    """Record mode without resume found an existing cassette: refusing to overwrite a recorded answer."""


def conflict_message(n: int) -> str:
    return (
        f"{n} cassette(s) for these requests already exist; cassettes are write-once. Use --resume to reuse "
        "them, --sample-offset to record independent samples, or delete them to re-record on purpose"
    )


class BudgetExceeded(RuntimeError):
    """Measured spend reached the run budget."""


class BudgetTracker:
    """Thread-safe running total of measured spend against a USD limit."""

    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = limit_usd
        self.spent = 0.0
        self._lock = threading.Lock()

    def add(self, cost: float) -> None:
        with self._lock:
            self.spent += cost

    def check(self) -> None:
        with self._lock:
            if self.spent >= self.limit_usd:
                raise BudgetExceeded(f"spent ${self.spent:.4f} of the ${self.limit_usd:.2f} budget")


class ReplayClient:
    """Answers only from cassettes; never calls a model."""

    def __init__(self, store: CassetteStore) -> None:
        self.store = store

    def complete(self, request: LLMRequest) -> LLMResponse:
        cached = self.store.get(request)
        if cached is not None:
            return cached
        return LLMResponse(
            error=f"no cassette {request.role}/{request.model}/{request.key()}.json; record it with --mode record",
            error_class="cassette_missing",
            attempts=0,
        )

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        return [self.complete(r) for r in requests]


class RecordingClient:
    """Calls `inner` for every request without a cassette and stores every model outcome (write-once)."""

    def __init__(
        self,
        inner: LLMClient,
        store: CassetteStore,
        resume: bool = False,
        budget: BudgetTracker | None = None,
    ) -> None:
        self.inner = inner
        self.store = store
        self.resume = resume
        self.budget = budget

    def complete(self, request: LLMRequest) -> LLMResponse:
        if self.resume:
            cached = self.store.get(request)
            if cached is not None:
                return cached
        elif self.store.exists(request):
            raise CassetteConflict(conflict_message(1) + f": {self.store.path_for(request)}")
        if self.budget is not None:
            self.budget.check()
        response = self.inner.complete(request)
        if self.budget is not None:
            self.budget.add(response.usage.cost_usd)
        if is_model_outcome(response):
            self.store.put(request, response)
        return response

    def complete_many(self, requests: list[LLMRequest]) -> list[LLMResponse]:
        """Concurrent `complete` (the inner client's `concurrency`, default 1); request order kept."""
        if not requests:
            return []
        workers = max(1, int(getattr(self.inner, "concurrency", 1)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(self.complete, requests))


def make_client(
    mode: str,
    *,
    store: CassetteStore | None = None,
    batch: bool = False,
    resume: bool = False,
    budget: BudgetTracker | None = None,
) -> LLMClient:
    """`replay` -> ReplayClient; `record` -> RecordingClient(AnthropicClient), or BatchClient with `batch`."""
    store = store or CassetteStore()
    if mode == "replay":
        return ReplayClient(store)
    if mode != "record":
        raise ValueError(f"unknown mode {mode!r}; expected 'replay' or 'record'")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "record mode needs ANTHROPIC_API_KEY: copy .env.example to .env and set it (or export it); "
            "use --mode replay to run offline from committed cassettes"
        )
    if batch:
        from aireview.llm.batch import BatchClient

        return BatchClient(store, budget=budget, resume=resume)
    from aireview.llm.anthropic_client import AnthropicClient

    return RecordingClient(AnthropicClient(), store, resume=resume, budget=budget)
