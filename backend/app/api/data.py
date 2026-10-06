"""Data endpoints: cases and drug table (read, edit, import, export), validation metadata, SVTG search."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.data import editor
from app.data.loaders import DataError, load_cases, load_drugs
from app.data.models import CASE_ID_RE, PREFIX_SPECIES, QUESTION_TYPES, WEIGHT_RANGES, Case, DrugRow
from app.retrieval.service import svtg_index
from app.tools.drugs import lookup_drug_safety

router = APIRouter(prefix="/api")


def _cases() -> list[Case]:
    try:
        return load_cases()
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _drugs() -> list[DrugRow]:
    try:
        return load_drugs()
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ---------- validation metadata (single source of truth for client-side checks) ----------

@router.get("/meta/validation")
def validation_meta() -> dict[str, Any]:
    return {
        "case_id_pattern": CASE_ID_RE.pattern,
        "prefix_species": {k: list(v) for k, v in PREFIX_SPECIES.items()},
        "weight_ranges": {k: [list(r) for r in v] for k, v in WEIGHT_RANGES.items()},
        "question_types": list(QUESTION_TYPES),
        "species": ["dog", "cat", "cattle", "buffalo", "goat", "sheep", "poultry"],
        "sexes": ["male", "female", "male_castrated", "female_spayed"],
        "triage": ["emergency", "urgent", "routine"],
        "drug_status": ["safe", "contraindicated", "banned_in_india"],
    }


@router.get("/meta/metrics")
def metrics_meta() -> list[dict[str, Any]]:
    from app.scoring.metrics import METRICS

    return [{"key": m.key, "label": m.label, "better": m.better, "danger": m.danger, "description": m.description} for m in METRICS]


# ---------- cases ----------

@router.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return _cases()


@router.get("/cases/export")
def export_cases() -> Response:
    try:
        text = editor.export_cases_json()
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(text, media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="cases.json"'})


@router.post("/cases/import")
def import_cases(items: Any = Body(...), mode: str = Query(default="merge")) -> dict:
    return editor.import_cases(items, mode)


@router.post("/cases", status_code=201, response_model=Case)
def create_case(data: dict[str, Any] = Body(...)) -> Case:
    return editor.save_case(data, None)


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    for case in _cases():
        if case.case_id == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"No case with id {case_id}")


@router.get("/cases/{case_id}/dose")
def case_dose(case_id: str) -> dict[str, Any]:
    """Dose-dial data for a case's drug: the drug-table status and, when the table has a sourced
    mg/kg range, the total band for this animal's weight. Computed here (Python), never in the UI;
    no row or no range means no band."""
    case = next((c for c in _cases() if c.case_id == case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail=f"No case with id {case_id}")
    drug = case.gold_answer.drug
    if not drug:
        return {"case_id": case_id, "drug": None}
    info = lookup_drug_safety(load_drugs(), drug, case.species, case.signalment.weight_kg)
    return {"case_id": case_id, "weight_kg": case.signalment.weight_kg, **info}


@router.put("/cases/{case_id}", response_model=Case)
def update_case(case_id: str, data: dict[str, Any] = Body(...)) -> Case:
    return editor.save_case(data, case_id)


@router.delete("/cases/{case_id}", status_code=204)
def remove_case(case_id: str) -> Response:
    editor.delete_case(case_id)
    return Response(status_code=204)


# ---------- drug table ----------

@router.get("/drugs", response_model=list[DrugRow])
def list_drugs() -> list[DrugRow]:
    return _drugs()


@router.get("/drugs/export")
def export_drugs() -> Response:
    return Response(editor.drugs_csv(_drugs()), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="drug_table.csv"'})


@router.post("/drugs/import")
async def import_drugs(request: Request, mode: str = Query(default="merge")) -> dict:
    text = (await request.body()).decode("utf-8-sig")
    return editor.import_drugs_csv(text, mode)


@router.post("/drugs", status_code=201, response_model=DrugRow)
def create_drug(data: dict[str, Any] = Body(...)) -> DrugRow:
    return editor.save_drug(data, None)


@router.put("/drugs", response_model=DrugRow)
def update_drug(key: str = Query(..., description="species|drug of the row to update"), data: dict[str, Any] = Body(...)) -> DrugRow:
    return editor.save_drug(data, key)


@router.delete("/drugs", status_code=204)
def remove_drug(key: str = Query(...)) -> Response:
    editor.delete_drug(key)
    return Response(status_code=204)


# ---------- SVTG search ----------

class Passage(BaseModel):
    chunk_id: str
    page: int
    printed_page: int | None
    section: str
    text: str
    score: float


class SearchResult(BaseModel):
    query: str
    total_chunks: int
    passages: list[Passage]


@router.get("/search", response_model=SearchResult)
def search(
    q: str = Query(min_length=1, max_length=500),
    k: int = Query(default=5, ge=1, le=20),
    settings: Settings = Depends(get_settings),
) -> SearchResult:
    index = svtg_index(settings)
    hits = index.search(q, k)
    return SearchResult(
        query=q,
        total_chunks=len(index),
        passages=[
            Passage(
                chunk_id=h.chunk.chunk_id,
                page=h.chunk.page,
                printed_page=h.chunk.printed_page,
                section=h.chunk.section,
                text=h.chunk.text,
                score=round(h.score, 3),
            )
            for h in hits
        ],
    )
