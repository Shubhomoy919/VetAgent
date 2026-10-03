"""Runs: start, stream (SSE), cancel, history; latest results per case; SVTG page passages."""

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.manager import RunConflict, manager, result_payload
from app.config import Settings, get_settings
from app.data.loaders import DataError, load_cases
from app.retrieval.service import svtg_index

router = APIRouter(prefix="/api")


class StartRun(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=200)
    conditions: list[str] | None = None
    interview: bool = False
    force: bool = False
    label: str = "bench"


@router.post("/runs", status_code=202)
def start_run(body: StartRun, settings: Settings = Depends(get_settings)) -> dict:
    try:
        state = manager.start(settings, body.case_ids, body.conditions, body.interview, body.force, body.label)
    except RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (ValueError, DataError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return state.summary()


@router.get("/runs/active")
def active_run() -> dict | None:
    a = manager.active()
    return a.summary() if a else None


COMPARE_METRICS = ("dx_top1", "triage_match", "dangerous", "under_triage", "false_safe", "illegal_drug",
                   "withdrawal_error", "missed_escalation")


@router.get("/runs/compare")
def compare_runs(a: str = Query(...), b: str = Query(...)) -> dict:
    """Two runs side by side: metric rates per shared condition, and cases whose verdict changed."""
    from app.scoring.metrics import build_scorecard
    from app.scoring.verdict import judge

    runs = {}
    for rid in (a, b):
        run = manager.store.get_run(rid)
        if run is None:
            raise HTTPException(status_code=404, detail=f"No run {rid}")
        runs[rid] = run
    cases = {c.case_id: c for c in load_cases()}
    res = {rid: manager.store.results(rid) for rid in (a, b)}
    sc = {rid: build_scorecard(runs[rid], res[rid], cases) for rid in (a, b)}
    shared = [c for c in sc[a]["conditions"] if c in sc[b]["conditions"]]

    metrics = []
    for key in COMPARE_METRICS:
        ma = next(m for m in sc[a]["metrics"] if m["key"] == key)
        mb = next(m for m in sc[b]["metrics"] if m["key"] == key)
        rows = {}
        for cond in shared:
            ra, rb = ma["by_condition"][cond], mb["by_condition"][cond]
            delta = rb["rate"] - ra["rate"] if ra["rate"] is not None and rb["rate"] is not None else None
            rows[cond] = {"a": ra, "b": rb, "delta": delta}
        metrics.append({"key": key, "label": ma["label"], "better": ma["better"], "by_condition": rows})

    def latest(rows: list[dict]) -> dict[tuple[str, str], dict]:
        out: dict[tuple[str, str], dict] = {}
        for r in rows:
            out[(r["case_id"], r["condition"])] = r
        return out

    la, lb = latest(res[a]), latest(res[b])
    changes = []
    for key in sorted(la.keys() & lb.keys()):
        cid, cond = key
        if cid not in cases or cond not in shared:
            continue
        va = judge(la[key]["answer"], cases[cid]) if la[key]["status"] == "ok" else None
        vb = judge(lb[key]["answer"], cases[cid]) if lb[key]["status"] == "ok" else None
        sa = {"status": la[key]["status"], "dx_top1": va and va["dx_top1"], "dangerous": va and va["dangerous"], "stamps": va["stamps"] if va else []}
        sb = {"status": lb[key]["status"], "dx_top1": vb and vb["dx_top1"], "dangerous": vb and vb["dangerous"], "stamps": vb["stamps"] if vb else []}
        if (sa["status"], sa["dx_top1"], sa["dangerous"], sa["stamps"]) != (sb["status"], sb["dx_top1"], sb["dangerous"], sb["stamps"]):
            changes.append({"case_id": cid, "condition": cond, "a": sa, "b": sb})

    return {"a": runs[a], "b": runs[b], "conditions": shared, "metrics": metrics, "changes": changes,
            "n_pairs": len([k for k in la.keys() & lb.keys() if k[1] in shared])}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str) -> dict:
    if not manager.cancel(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} is not running")
    return {"run_id": run_id, "cancelling": True}


def _sse(event: dict) -> str:
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"


@router.get("/runs/{run_id}/events")
async def run_events(run_id: str, request: Request) -> StreamingResponse:
    state = manager.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"No live event stream for run {run_id} (it may have finished before the server restarted)")

    async def stream():
        sent = 0
        last_beat = time.monotonic()
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                return
            batch = state.events_since(sent)
            for ev in batch:
                yield _sse(ev)
            sent += len(batch)
            if state.closed and sent >= len(state.events):
                return
            if time.monotonic() - last_beat > 15:
                yield ": keep-alive\n\n"
                last_beat = time.monotonic()
            await asyncio.sleep(0.05)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.get("/runs")
def list_runs(limit: int = Query(default=50, ge=1, le=500)) -> list[dict]:
    return manager.store.list_runs(limit)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    run = manager.store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}")
    cases = {c.case_id: c for c in load_cases()}
    results = []
    for r in manager.store.results(run_id):
        p = result_payload(r, cases.get(r["case_id"]), r["id"])
        p["created_at"] = r["created_at"]
        results.append(p)
    return {**run, "results": results}


@router.get("/results/latest")
def latest_results(interview: bool = False) -> dict[str, dict[str, dict]]:
    """{case_id: {condition: result summary with verdict}} — no traces."""
    cases = {c.case_id: c for c in load_cases()}
    out: dict[str, dict[str, dict]] = {}
    for r in manager.store.latest_results(interview):
        p = result_payload(r, cases.get(r["case_id"]), r["id"])
        p.update(run_id=r["run_id"], provider=r["provider"], model=r["model"], created_at=r["created_at"])
        out.setdefault(r["case_id"], {})[r["condition"]] = p
    return out


@router.get("/results/{result_id}")
def get_result(result_id: int) -> dict:
    r = manager.store.get_result(result_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"No result {result_id}")
    case = next((c for c in load_cases() if c.case_id == r["case_id"]), None)
    p = result_payload(r, case, r["id"])
    p.update(trace=r["trace"], run_id=r["run_id"], provider=r["provider"], model=r["model"], created_at=r["created_at"])
    return p


@router.get("/svtg/pages/{page}")
def svtg_page(page: int, settings: Settings = Depends(get_settings)) -> dict:
    index = svtg_index(settings)
    chunks = [c for c in index.chunks if c.page == page]
    if not chunks:
        raise HTTPException(status_code=404, detail=f"No indexed SVTG text on PDF page {page}")
    return {
        "page": page,
        "printed_page": chunks[0].printed_page,
        "chunks": [{"chunk_id": c.chunk_id, "section": c.section, "text": c.text} for c in chunks],
    }
