"""Runs: create, run one step at a time (SSE or JSON), finish, cancel, history; latest results per case;
SVTG page passages."""

import asyncio
import json
import queue
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.agent.manager import BudgetExceeded, RunConflict, StepCancelled, StepError, manager, result_payload
from app.config import Settings, get_settings
from app.data.loaders import DataError, load_cases
from app.retrieval.service import svtg_index
from app.security import is_admin, redact, require_admin

router = APIRouter(prefix="/api")


class StartRun(BaseModel):
    case_ids: list[str] = Field(min_length=1, max_length=500)
    conditions: list[str] | None = Field(default=None, max_length=5)
    interview: bool = False
    force: bool = False
    label: str = Field(default="bench", max_length=80)


class StepBody(BaseModel):
    case_id: str = Field(min_length=1, max_length=40)
    condition: str = Field(min_length=2, max_length=4)


class FinishBody(BaseModel):
    cancelled: bool = False


@router.post("/runs", status_code=202, dependencies=[Depends(require_admin)])
def start_run(body: StartRun, settings: Settings = Depends(get_settings)) -> dict:
    """Create a run. The client then calls /runs/{id}/step for each case and condition, in order."""
    try:
        return manager.start(settings, body.case_ids, body.conditions, body.interview, body.force, body.label)
    except RunConflict as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except BudgetExceeded as e:
        raise HTTPException(status_code=429, detail=str(e)) from e
    except (ValueError, DataError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/budget")
def budget(settings: Settings = Depends(get_settings)) -> dict:
    """Today's live-model token use against MAX_DAILY_TOKENS, plus the per-run case limit."""
    return {**manager.budget(settings), "max_cases_per_run": settings.max_cases_per_run}


@router.get("/runs/active")
def active_run(settings: Settings = Depends(get_settings)) -> dict | None:
    """The run still in progress, with the steps already done, so a reloaded page can continue it."""
    return manager.active(settings)


def _sse(event: dict) -> str:
    return f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"


@router.post("/runs/{run_id}/step", dependencies=[Depends(require_admin)])
async def run_step(run_id: str, body: StepBody, request: Request, settings: Settings = Depends(get_settings)):
    """Run one case through one condition and store the result.

    With `Accept: text/event-stream` the agent steps stream as server-sent events (result_started, step…,
    result_done, and run_error when the run has to stop). Otherwise the response is JSON: the result_done data
    plus the full event list. Either way the step ends within STEP_DEADLINE_S; a step still working then is
    stored as "timeout" and can be retried."""
    try:
        ctx = await run_in_threadpool(manager.prepare_step, settings, run_id, body.case_id, body.condition)
    except StepError as e:
        raise HTTPException(status_code=e.status, detail=e.message) from e

    if "text/event-stream" not in request.headers.get("accept", ""):
        events: list[dict] = []
        done = await run_in_threadpool(manager.run_step, settings, ctx,
                                       lambda t, d: events.append({"id": len(events) + 1, "type": t, "data": d}))
        return {**done, "events": events}

    q: queue.Queue = queue.Queue()
    cancel = threading.Event()

    def work() -> None:
        try:
            manager.run_step(settings, ctx, lambda t, d: q.put((t, d)), cancel)
        except StepCancelled:
            pass
        except Exception as e:  # reported in the stream; never a traceback
            q.put(("step_error", {"case_id": body.case_id, "condition": body.condition,
                                  "error": redact(f"{type(e).__name__}: {e}", settings)}))
        finally:
            q.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def stream():
        n = 0
        last = time.monotonic()
        try:
            while True:
                try:
                    item = q.get_nowait()
                except queue.Empty:
                    if await request.is_disconnected():
                        return
                    if time.monotonic() - last > 15:
                        yield ": keep-alive\n\n"
                        last = time.monotonic()
                    await asyncio.sleep(0.05)
                    continue
                if item is None:
                    return
                n += 1
                last = time.monotonic()
                yield _sse({"id": n, "type": item[0], "data": item[1]})
        finally:
            cancel.set()  # client gone: the worker stops at its next agent step

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/runs/{run_id}/finish", dependencies=[Depends(require_admin)])
def finish_run(run_id: str, body: FinishBody | None = None) -> dict:
    """Close a run after its last step (or when the user cancels it)."""
    try:
        return manager.finish(run_id, "cancelled" if body and body.cancelled else None)
    except StepError as e:
        raise HTTPException(status_code=e.status, detail=e.message) from e


COMPARE_METRICS = ("dx_top1", "triage_match", "dangerous", "under_triage", "false_safe", "illegal_drug",
                   "withdrawal_error", "missed_escalation")


@router.get("/runs/compare")
def compare_runs(a: str = Query(max_length=64), b: str = Query(max_length=64)) -> dict:
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


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_admin)])
def cancel_run(run_id: str) -> dict:
    if not manager.cancel(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} is not running")
    return {"run_id": run_id, "cancelling": True}


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


@router.get("/results")
def case_results(case_id: str = Query(min_length=1, max_length=40), limit: int = Query(default=100, ge=1, le=500)) -> list[dict]:
    """All stored results for one case across runs (newest first), with verdicts, without traces."""
    case = next((c for c in load_cases() if c.case_id == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case {case_id}")
    out = []
    for r in manager.store.case_results(case_id, limit):
        p = result_payload(r, case, r["id"])
        p.update(run_id=r["run_id"], provider=r["provider"], model=r["model"], created_at=r["created_at"])
        out.append(p)
    return out


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


# DAHD's own copy of the guidelines (Department of Animal Husbandry and Dairying, Government of India).
SVTG_SOURCE_URL = "https://dahd.gov.in/sites/default/files/2024-10/StandardVeterinaryTreatment.pdf"


def public_pages() -> set[int]:
    """Pages cited by stored answers or by a case's gold answer."""
    gold = {cit.page for c in load_cases() for cit in c.gold_answer.citations if cit.page}
    return manager.store.cited_pages() | gold


@router.get("/svtg/pages/{page}")
def svtg_page(request: Request, page: int = Path(ge=1, le=5000), settings: Settings = Depends(get_settings)) -> dict:
    """Indexed SVTG text for one PDF page. Public visitors get only pages that a stored answer cites;
    the PDF itself is never served."""
    if not is_admin(request, settings) and page not in public_pages():
        raise HTTPException(status_code=404, detail=f"PDF page {page} is not cited by any stored answer")
    index = svtg_index(settings)
    chunks = [c for c in index.chunks if c.page == page]
    if not chunks:
        raise HTTPException(status_code=404, detail=f"No indexed SVTG text on PDF page {page}")
    return {
        "page": page,
        "printed_page": chunks[0].printed_page,
        "chunks": [{"chunk_id": c.chunk_id, "section": c.section, "text": c.text} for c in chunks],
        "source": {"title": "Standard Veterinary Treatment Guidelines (SVTG), DAHD, Government of India", "url": SVTG_SOURCE_URL},
    }
