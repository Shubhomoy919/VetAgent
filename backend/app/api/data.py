"""Read-only data endpoints: cases, drug table and SVTG search."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.data.loaders import DataError, load_cases, load_drugs
from app.data.models import Case, DrugRow
from app.retrieval.service import svtg_index

router = APIRouter(prefix="/api")


def _cases() -> list[Case]:
    try:
        return load_cases()
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/cases", response_model=list[Case])
def list_cases() -> list[Case]:
    return _cases()


@router.get("/cases/{case_id}", response_model=Case)
def get_case(case_id: str) -> Case:
    for case in _cases():
        if case.case_id == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"No case with id {case_id}")


@router.get("/drugs", response_model=list[DrugRow])
def list_drugs() -> list[DrugRow]:
    try:
        return load_drugs()
    except DataError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
