"""GET /api/health — readiness of the PDF, data files and LLM provider.

Never exposes keys: only `key_present: true/false`.
"""

import csv
import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pymupdf
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import DATA_DIR, REPO_ROOT, Settings, get_settings

router = APIRouter()


class Counts(BaseModel):
    cases: int
    drugs: int
    runs: int


class Health(BaseModel):
    status: Literal["ok"]
    provider: str
    configured_provider: str
    mode: Literal["live", "demo"]
    model: str
    key_present: bool
    pdf_path: str
    pdf_loaded: bool
    pages: int
    chunks: int
    counts: Counts


@lru_cache(maxsize=4)
def _pdf_pages(path: str, mtime: float) -> int:
    with pymupdf.open(path) as doc:
        return doc.page_count


def pdf_status(path: Path) -> tuple[bool, int]:
    if not path.is_file():
        return False, 0
    try:
        return True, _pdf_pages(str(path), path.stat().st_mtime)
    except Exception:
        return False, 0


def count_cases(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    return len(data) if isinstance(data, list) else 0


def count_drugs(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open(encoding="utf-8", newline="") as f:
            return sum(1 for _ in csv.DictReader(f))
    except (OSError, csv.Error):
        return 0


def count_runs(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            return conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    except sqlite3.Error:
        return 0


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


@router.get("/api/health", response_model=Health)
def health(settings: Settings = Depends(get_settings)) -> Health:
    pdf_loaded, pages = pdf_status(settings.pdf_path)
    provider = settings.effective_provider
    return Health(
        status="ok",
        provider=provider,
        configured_provider=settings.llm_provider,
        mode="demo" if provider == "demo" else "live",
        model=settings.model_id,
        key_present=settings.key_present,
        pdf_path=_display_path(settings.pdf_path),
        pdf_loaded=pdf_loaded,
        pages=pages,
        # The chunk index is built in M2 (SVTG ingestion); until then there are none.
        chunks=0,
        counts=Counts(
            cases=count_cases(DATA_DIR / "cases.json"),
            drugs=count_drugs(DATA_DIR / "drug_table.csv"),
            runs=count_runs(DATA_DIR / "runs.db"),
        ),
    )
