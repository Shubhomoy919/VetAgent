"""Human review of stored answers, and agreement statistics (percent agreement, Cohen's kappa)."""

from itertools import combinations
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.agent.manager import manager
from app.api.scorecard import default_run_id
from app.data.loaders import load_cases
from app.scoring.stats import cohen_kappa, wilson
from app.scoring.verdict import judge
from app.tools.registry import case_view

from app.security import require_admin  # noqa: E402

router = APIRouter(prefix="/api/review", dependencies=[Depends(require_admin)])


class ReviewIn(BaseModel):
    result_id: int
    reviewer: str = Field(min_length=1, max_length=80)
    rating: Literal["acceptable", "unacceptable", "unsure"]
    note: str = Field(default="", max_length=2000)


def _run_or_404(run_id: str | None) -> dict[str, Any]:
    rid = run_id or default_run_id()
    if rid is None:
        raise HTTPException(status_code=404, detail="No runs to review yet. Run cases from the Bench first.")
    run = manager.store.get_run(rid)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {rid}")
    return run


def _latest_ok(run_id: str) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for r in manager.store.results(run_id):
        latest[(r["case_id"], r["condition"])] = r
    return [r for r in latest.values() if r["status"] == "ok" and r["answer"]]


@router.get("/queue")
def queue(run_id: str | None = Query(default=None, max_length=64), reviewer: str = Query(default="", max_length=80)) -> dict[str, Any]:
    run = _run_or_404(run_id)
    cases = {c.case_id: c for c in load_cases()}
    mine = {v["result_id"]: v for v in manager.store.reviews_for_run(run["id"]) if v["reviewer"] == reviewer}
    items = []
    for r in sorted(_latest_ok(run["id"]), key=lambda x: (x["case_id"], x["condition"])):
        case = cases.get(r["case_id"])
        if case is None:
            continue
        v = judge(r["answer"], case)
        rev = mine.get(r["id"])
        items.append({
            "result_id": r["id"],
            "case_id": r["case_id"],
            "condition": r["condition"],
            "interview": r["interview"],
            "answer": r["answer"],
            "rules_fired": r["rules_fired"],
            "case": case_view(case),
            "question_type": case.question_type,
            "gold": case.gold_answer.model_dump(),
            "auto": {"dangerous": v["dangerous"], "stamps": v["stamps"], "dx_top1": v["dx_top1"]},
            "review": {"rating": rev["rating"], "note": rev["note"]} if rev else None,
        })
    return {"run": run, "items": items}


@router.put("")
def save(body: ReviewIn) -> dict[str, Any]:
    try:
        return manager.store.save_review(body.result_id, body.reviewer.strip(), body.rating, body.note)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("")
def remove(result_id: int = Query(...), reviewer: str = Query(...)) -> dict[str, Any]:
    if not manager.store.delete_review(result_id, reviewer):
        raise HTTPException(status_code=404, detail="No such review")
    return {"deleted": True}


def _agreement(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b)
    return {
        "n": n,
        "agree": agree,
        "percent": agree / n if n else None,
        "kappa": cohen_kappa(pairs),
        # rows = first rater, cols = second rater; True = acceptable
        "matrix": {
            "acc_acc": sum(1 for a, b in pairs if a and b),
            "acc_unacc": sum(1 for a, b in pairs if a and not b),
            "unacc_acc": sum(1 for a, b in pairs if not a and b),
            "unacc_unacc": sum(1 for a, b in pairs if not a and not b),
        },
    }


@router.get("/stats")
def stats(run_id: str | None = Query(default=None)) -> dict[str, Any]:
    """Reviewer vs automatic scorer, reviewer vs reviewer, and reviewer-judged acceptability per condition.

    Automatic label: acceptable = no dangerous error. 'unsure' ratings are excluded from agreement.
    """
    run = _run_or_404(run_id)
    cases = {c.case_id: c for c in load_cases()}
    results = {r["id"]: r for r in _latest_ok(run["id"])}
    auto = {rid: not judge(r["answer"], cases[r["case_id"]])["dangerous"]
            for rid, r in results.items() if r["case_id"] in cases}
    reviews = [v for v in manager.store.reviews_for_run(run["id"]) if v["result_id"] in auto]

    by_reviewer: dict[str, dict[int, str]] = {}
    for v in reviews:
        by_reviewer.setdefault(v["reviewer"], {})[v["result_id"]] = v["rating"]

    reviewers = []
    for name, ratings in sorted(by_reviewer.items()):
        decided = {rid: rt == "acceptable" for rid, rt in ratings.items() if rt != "unsure"}
        per_cond: dict[str, dict[str, Any]] = {}
        for cond in sorted({results[rid]["condition"] for rid in decided}):
            vals = [ok for rid, ok in decided.items() if results[rid]["condition"] == cond]
            k, n = sum(vals), len(vals)
            ci = wilson(k, n)
            per_cond[cond] = {"k": k, "n": n, "rate": k / n if n else None, "lo": ci[0] if ci else None, "hi": ci[1] if ci else None}
        reviewers.append({
            "reviewer": name,
            "rated": len(ratings),
            "unsure": sum(1 for rt in ratings.values() if rt == "unsure"),
            "vs_auto": _agreement([(decided[rid], auto[rid]) for rid in decided]),
            "acceptable_by_condition": per_cond,
        })

    pairs = []
    for a, b in combinations(sorted(by_reviewer), 2):
        ra, rb = by_reviewer[a], by_reviewer[b]
        shared = [rid for rid in ra.keys() & rb.keys() if ra[rid] != "unsure" and rb[rid] != "unsure"]
        pairs.append({"a": a, "b": b, **_agreement([(ra[rid] == "acceptable", rb[rid] == "acceptable") for rid in shared])})

    return {"run": run, "items_total": len(auto), "reviewers": reviewers, "pairs": pairs}
