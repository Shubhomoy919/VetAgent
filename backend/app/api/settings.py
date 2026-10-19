"""Settings: view and edit non-secret settings, test the provider connection, usage totals.

API keys are never returned or accepted here. They stay in .env; the page shows only key_present.
"""

import json
import os
import time
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.agent.manager import manager
from app.api.health import pdf_status
from app.config import EDITABLE_FIELDS, OVERRIDES_PATH, Settings, get_settings, load_overrides, reset_settings_cache
from app.llm.base import LLMError, LLMRequest, Message
from app.llm.factory import get_provider

from app.security import require_admin  # noqa: E402

router = APIRouter(prefix="/api/settings", dependencies=[Depends(require_admin)])


def _view(s: Settings) -> dict[str, Any]:
    loaded, pages = pdf_status(s.pdf_path)
    overrides = load_overrides()
    return {
        "values": {k: getattr(s, k) for k in EDITABLE_FIELDS},
        "overridden": sorted(overrides),
        "effective_provider": s.effective_provider,
        "mode": "demo" if s.effective_provider == "demo" else "live",
        "model": s.model_id,
        "key_present": s.key_present,
        "key_hint": {
            "gemini": "Set GEMINI_API_KEY in the server environment (.env locally)",
            "openai_compatible": "Set OPENAI_API_KEY and OPENAI_BASE_URL in the server environment (.env locally)",
            "demo": "No key needed",
        }[s.llm_provider],
        "pdf": {"path": s.svtg_pdf_path, "exists": s.pdf_path.is_file(), "loaded": loaded, "pages": pages},
        "overrides_file": f"DATA_DIR/{OVERRIDES_PATH.name}",
    }


@router.get("")
def get_all() -> dict[str, Any]:
    return _view(get_settings())


@router.put("")
def update(values: dict[str, Any] = Body(...)) -> Any:
    unknown = sorted(set(values) - set(EDITABLE_FIELDS))
    if unknown:
        return JSONResponse(
            status_code=422,
            content={"detail": "These settings cannot be changed here", "errors": [{"loc": [k], "msg": "not editable (keys belong in .env)"} for k in unknown]},
        )
    merged = {**load_overrides(), **values}
    # A blank price that was sent means "not set" (only for keys actually sent, so .env prices aren't hidden).
    for k in ("price_input_per_mtok", "price_output_per_mtok"):
        if k in values and values[k] in ("", None):
            merged[k] = None
    try:
        candidate = Settings(**merged)  # type: ignore[arg-type]
    except ValidationError as e:
        return JSONResponse(
            status_code=422,
            content={"detail": "Settings failed validation", "errors": [{"loc": list(x["loc"]), "msg": x["msg"]} for x in e.errors()]},
        )
    # Check the PDF only when its path is being changed, so other settings can still be saved without it.
    if "svtg_pdf_path" in values and not candidate.pdf_path.is_file():
        return JSONResponse(status_code=422, content={"detail": "PDF not found", "errors": [{"loc": ["svtg_pdf_path"], "msg": f"No file at {candidate.svtg_pdf_path}"}]})
    clean = {k: getattr(candidate, k) for k in merged}
    OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERRIDES_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    os.replace(tmp, OVERRIDES_PATH)
    reset_settings_cache()
    return _view(get_settings())


@router.delete("")
def reset() -> dict[str, Any]:
    """Remove all overrides; .env values apply again."""
    if OVERRIDES_PATH.is_file():
        OVERRIDES_PATH.unlink()
    reset_settings_cache()
    return _view(get_settings())


@router.post("/test")
def test_connection() -> dict[str, Any]:
    s = get_settings()
    if s.effective_provider == "demo":
        reason = "no API key configured" if s.llm_provider != "demo" else "provider set to demo"
        return {"ok": True, "provider": "demo", "model": "demo", "latency_ms": 0, "reply": None,
                "message": f"Demo mode ({reason}): nothing to connect to."}
    provider = get_provider(s)
    req = LLMRequest(
        system="You are a connectivity check. Reply with the requested JSON only.",
        messages=[Message("user", 'Reply with exactly: {"ok": true}')],
        json_mode=True,
        temperature=0.0,
    )
    t = time.perf_counter()
    try:
        resp = provider.complete(req)
    except LLMError as e:
        return {"ok": False, "provider": provider.name, "model": provider.model,
                "latency_ms": int((time.perf_counter() - t) * 1000), "reply": None, "message": str(e)}
    return {"ok": True, "provider": provider.name, "model": resp.model, "latency_ms": resp.latency_ms,
            "tokens": resp.tokens_in + resp.tokens_out, "reply": resp.text[:200], "message": "Connected."}


@router.get("/usage")
def usage() -> dict[str, Any]:
    rows = manager.store.usage_totals()
    for r in rows:
        if r["cost_unknown"]:
            r["cost_usd"] = None
    total_tokens = sum(r["tokens_in"] + r["tokens_out"] for r in rows)
    costs = [r["cost_usd"] for r in rows]
    return {
        "by_model": rows,
        "total_results": sum(r["results"] for r in rows),
        "total_tokens": total_tokens,
        "total_cost_usd": None if any(c is None for c in costs) else round(sum(costs), 6),  # type: ignore[arg-type]
    }
