"""Scorecard for a run, plus CSV / JSON export."""

import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.agent.manager import manager
from app.data.loaders import DataError, load_cases
from app.scoring.metrics import CSV_HEADER, build_scorecard, scorecard_csv_rows

router = APIRouter(prefix="/api/scorecard")

FINISHED = ("done", "done_with_errors", "cancelled")


def default_run_id() -> str | None:
    """Most recent finished run that covers more than one case; else the most recent with any result."""
    runs = manager.store.list_runs(200)
    for r in runs:
        if r["status"] in FINISHED and r["n_done"] > 0 and len(r["case_ids"]) > 1:
            return r["id"]
    for r in runs:
        if r["n_done"] > 0:
            return r["id"]
    return None


def scorecard_for(run_id: str | None) -> dict:
    rid = run_id or default_run_id()
    if rid is None:
        raise HTTPException(status_code=404, detail="No runs with results yet. Run cases from the Bench first.")
    run = manager.store.get_run(rid)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {rid}")
    try:
        cases = {c.case_id: c for c in load_cases()}
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return build_scorecard(run, manager.store.results(rid), cases)


@router.get("")
def scorecard(run_id: str | None = Query(default=None)) -> dict:
    return scorecard_for(run_id)


@router.get("/export.csv")
def export_csv(run_id: str | None = Query(default=None)) -> Response:
    sc = scorecard_for(run_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(CSV_HEADER)
    w.writerows(scorecard_csv_rows(sc))
    name = f"scorecard-{sc['run']['id']}.csv"
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export.json")
def export_json(run_id: str | None = Query(default=None)) -> Response:
    sc = scorecard_for(run_id)
    name = f"scorecard-{sc['run']['id']}.json"
    return Response(json.dumps(sc, indent=2), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
