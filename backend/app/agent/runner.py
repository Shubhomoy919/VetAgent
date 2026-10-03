"""Run case × condition with caching and storage.

Cache key = sha256(provider, model, condition, interview, prompt_version, case content, max_steps).
A cached result is reused unless force=True; it is still stored as a new result row (cached=1).
"""

import hashlib
import json
import time
from collections.abc import Callable
from typing import Any

from app.agent.conditions import AgentError, ConditionId, Ctx, run_condition
from app.agent.prompts import PROMPT_VERSION
from app.agent.trace import Step, Trace
from app.config import Settings
from app.data.models import Case, DrugRow
from app.llm.base import LLMError, Provider, QuotaExhausted
from app.retrieval.search import SearchIndex
from app.storage.db import Store


def cache_key(provider: Provider, condition: str, case: Case, interview: bool, settings: Settings) -> str:
    material = json.dumps(
        {
            "provider": provider.name,
            "model": provider.model,
            "condition": condition,
            "interview": interview,
            "prompt_version": PROMPT_VERSION,
            "max_steps": settings.max_steps,
            "temperature": settings.temperature,
            "case": case.model_dump(mode="json"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def run_one(
    *,
    case: Case,
    condition: ConditionId,
    provider: Provider,
    settings: Settings,
    index: SearchIndex,
    drugs: list[DrugRow],
    store: Store | None = None,
    interview: bool = False,
    force: bool = False,
    on_step: Callable[[Step], None] | None = None,
) -> dict[str, Any]:
    key = cache_key(provider, condition, case, interview, settings)
    base = {"case_id": case.case_id, "condition": condition, "interview": interview, "cache_key": key}

    if store and not force:
        hit = store.cache_get(key)
        if hit:
            if on_step:
                on_step(Step(index=0, kind="cache", name="cache_hit", note=f"reused cached result {key[:12]}"))
            return {**base, **hit, "cached": True}

    trace = Trace(on_step=on_step)
    ctx = Ctx(condition=condition, case=case, provider=provider, settings=settings, index=index, drugs=drugs,
              trace=trace, interview=interview)
    t = time.perf_counter()
    try:
        res = run_condition(ctx)
        payload: dict[str, Any] = {
            "status": "ok",
            "answer": res.answer.model_dump(),
            "error": None,
            "rules_fired": res.rules_fired,
            "owner_questions": res.owner_questions,
        }
    except (AgentError, LLMError) as e:
        payload = {"status": "error", "answer": None, "error": str(e), "rules_fired": [], "owner_questions": []}
        if isinstance(e, QuotaExhausted):
            payload["quota_exhausted"] = True
    payload.update(
        trace=[s.to_dict() for s in trace.steps],
        steps=trace.tool_calls,
        tokens_in=trace.tokens_in,
        tokens_out=trace.tokens_out,
        cost_usd=settings.cost_usd(trace.tokens_in, trace.tokens_out),
        latency_ms=int((time.perf_counter() - t) * 1000),
    )
    if store and payload["status"] == "ok":
        store.cache_put(
            key,
            {"provider": provider.name, "model": provider.model, "condition": condition, "case_id": case.case_id,
             "prompt_version": PROMPT_VERSION, "interview": interview},
            payload,
        )
    return {**base, **payload, "cached": False}
