"""Server-side OpenRouter adapter. The only place a model is called.

Budget enforcement happens *before* each call (call count, per-run cost,
overall credit pool). It is a software guard, not a billing cap: a call that
starts under budget can still finish over it (in-flight overshoot). The worst
case per call is bounded by max_output_tokens plus the prompt size.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from flowlens.config import Settings

# Shared across runs in this process (runs execute in worker threads).
_call_slots: threading.BoundedSemaphore | None = None
_slots_lock = threading.Lock()


def _slots(n: int) -> threading.BoundedSemaphore:
    global _call_slots
    with _slots_lock:
        if _call_slots is None:
            _call_slots = threading.BoundedSemaphore(n)
        return _call_slots


class BudgetExceeded(Exception):
    pass


class SchemaRejected(Exception):
    pass


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reported_cost_usd: float | None
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    reasoning_tokens: int | None = None


class LLMClient(Protocol):
    model: str
    is_mock: bool

    async def complete(self, messages: list[dict[str, str]], max_tokens: int,
                       reasoning_tokens: int | None = None) -> LLMResponse: ...


def reasoning_request(reasoning_tokens: int | None) -> dict:
    """Hidden-reasoning setting sent to the provider. Hidden reasoning shares the output cap.

    None: effort "low" (the default for every call). 0: effort "minimal", used to retry a reply that
    reasoning cut off. A positive number: an explicit token budget. Recorded calls showed that
    google/gemini-3-flash-preview does not honour token budgets (run_156b7b84dc3b: 1342 and 2684
    reasoning tokens against a 384 budget; 88 of 230 tester calls over 600), while effort "low"
    stayed small (explore calls: median 0, 2 of 877 truncated).
    """
    if reasoning_tokens is None:
        return {"effort": "low", "exclude": True}
    if reasoning_tokens == 0:
        return {"effort": "minimal", "exclude": True}
    return {"max_tokens": reasoning_tokens, "exclude": True}


class OpenRouterClient:
    is_mock = False
    supports_schema = False  # set from FLOWLENS_PROVIDER_JSON_SCHEMA; off by default (see __init__)

    def __init__(self, settings: Settings):
        if not settings.has_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set in .env")
        self.model = settings.openrouter_model
        self._base = settings.openrouter_base_url.rstrip("/")
        self._key = settings.openrouter_api_key.get_secret_value().strip()  # type: ignore[union-attr]
        self._timeout = settings.flowlens_model_timeout_s
        self._slots = _slots(settings.flowlens_max_concurrent_model_calls)
        # Provider-side JSON schema made gemini-3-flash loop inside string fields and omit optional
        # fields (batch-postfix-ticket-desk). Replies are validated locally either way.
        self.supports_schema = settings.flowlens_provider_json_schema

    async def complete(self, messages: list[dict[str, str]], max_tokens: int,
                       reasoning_tokens: int | None = None, schema: dict | None = None) -> LLMResponse:
        if schema is not None:
            try:
                return await self._complete(messages, max_tokens, reasoning_tokens, schema)
            except SchemaRejected:
                pass  # provider refused structured output: fall back to plain JSON mode (still validated locally)
        return await self._complete(messages, max_tokens, reasoning_tokens, None)

    async def _complete(self, messages, max_tokens, reasoning_tokens, schema) -> LLMResponse:
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0,
            "response_format": ({"type": "json_schema",
                                 "json_schema": {"name": "reply", "strict": False, "schema": schema}}
                                if schema is not None else {"type": "json_object"}),
            "reasoning": reasoning_request(reasoning_tokens),
            "usage": {"include": True},
        }
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "X-Title": "FlowLens",
        }
        # Several workers share one event loop in queue mode, so wait for a slot off-loop;
        # a blocking acquire here would freeze the loop while the slot holders await I/O.
        await asyncio.to_thread(self._slots.acquire)
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                r = await client.post(f"{self._base}/chat/completions", json=body, headers=headers)
            latency = int((time.perf_counter() - t0) * 1000)
        finally:
            self._slots.release()
        if r.status_code == 400 and schema is not None:
            raise SchemaRejected(r.text[:200])
        if r.status_code != 200:
            raise RuntimeError(f"OpenRouter HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"OpenRouter error: {str(data['error'])[:300]}")
        usage = data.get("usage") or {}
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        details = usage.get("completion_tokens_details") or {}
        return LLMResponse(
            content=msg.get("content") or "",
            model=data.get("model", self.model),
            provider=data.get("provider"),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            reported_cost_usd=float(usage["cost"]) if usage.get("cost") is not None else None,
            latency_ms=latency,
            finish_reason=choice.get("finish_reason"),
            reasoning_tokens=details.get("reasoning_tokens"),
            raw={k: v for k, v in data.items() if k != "choices"} | {"message": msg},
        )


class ScriptedClient:
    """Test stand-in. Runs using it are labelled mocked_model and never live."""

    is_mock = True
    model = "scripted-test-model"

    def __init__(self, script):
        self._script = script  # callable(messages) -> str

    async def complete(self, messages, max_tokens, reasoning_tokens=None):
        return LLMResponse(
            content=self._script(messages), model=self.model, provider="none",
            prompt_tokens=0, completion_tokens=0, total_tokens=0, reported_cost_usd=0.0, latency_ms=0,
        )


def check_budget(*, calls_used: int, max_calls: int, run_cost: float, run_limit: float,
                 pool_spent: float, pool_limit: float) -> None:
    if calls_used >= max_calls:
        raise BudgetExceeded(f"model-call limit reached ({calls_used}/{max_calls})")
    if run_cost >= run_limit:
        raise BudgetExceeded(f"per-run cost limit reached (US${run_cost:.4f} / US${run_limit:.2f})")
    if pool_spent >= pool_limit:
        raise BudgetExceeded(f"overall credit budget reached (US${pool_spent:.4f} / US${pool_limit:.2f})")
