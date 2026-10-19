"""GET /api/health — version, benchmark hash, readiness of the database, the SVTG passages and the LLM provider.

Never exposes keys or the database URL: only `key_present: true/false` and the database engine name.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app import __version__
from app.config import Settings, get_settings
from app.data.benchmark import benchmark_info
from app.data.loaders import DataError, load_cases, load_drugs
from app.retrieval.service import index_status
from app.security import is_admin
from app.storage.db import DatabaseNotConfigured, database_url, describe_url, get_store

router = APIRouter()

SEED_HINT = "Run the migrations and the seed script (docs/DEPLOY.md, step 5)."


class Counts(BaseModel):
    cases: int
    drugs: int
    runs: int


class Benchmark(BaseModel):
    version: str
    hash: str
    short_hash: str
    frozen: bool
    frozen_on: str


class Database(BaseModel):
    ok: bool
    engine: Literal["sqlite", "postgresql", "none"]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: Literal["development", "production"]
    mode: Literal["public", "admin"]
    access_required: bool
    llm_mode: Literal["live", "demo"]
    provider: str
    configured_provider: str
    model: str
    key_present: bool
    index_loaded: bool
    chunks: int
    source_pages: int
    counts: Counts
    benchmark: Benchmark | None
    database: Database
    data_errors: list[str]
    warnings: list[str]


@router.get("/api/health", response_model=Health)
def health(request: Request, settings: Settings = Depends(get_settings)) -> Health:
    provider = settings.effective_provider
    errors: list[str] = []
    warnings: list[str] = []

    try:
        url = database_url()
        store = get_store()
        db = Database(ok=store.ping(), engine=describe_url(url))  # type: ignore[arg-type]
    except DatabaseNotConfigured as e:
        store, db = None, Database(ok=False, engine="none")
        errors.append(str(e))
    except Exception as e:  # unreachable or misconfigured database must not take health down
        store, db = None, Database(ok=False, engine="none")
        errors.append(f"Database unavailable ({type(e).__name__})")
    if store is not None and not db.ok:
        errors.append("Database unreachable")

    n_cases = n_drugs = n_runs = 0
    bench = None
    idx = {"index_loaded": False, "chunks": 0, "source_pages": 0}
    if db.ok and store is not None:
        try:
            n_cases = len(load_cases())
        except DataError as e:
            errors.append(f"{e} {SEED_HINT}" if "seed" not in str(e) else str(e))
        try:
            n_drugs = len(load_drugs())
        except DataError as e:
            errors.append(str(e))
        try:
            bench = Benchmark(**{k: v for k, v in benchmark_info().items() if k in Benchmark.model_fields})
        except DataError:
            bench = None
        try:
            n_runs = store.count_runs()
        except Exception as e:
            errors.append(f"Runs could not be counted ({type(e).__name__}). {SEED_HINT}")
        idx = index_status()
        if not idx["index_loaded"]:
            warnings.append("SVTG passages are not loaded: retrieval returns nothing and cited passages cannot be "
                            "shown. " + SEED_HINT)

    return Health(
        status="ok" if db.ok and not errors and not warnings else "degraded",
        version=__version__,
        environment=settings.app_env,
        mode="admin" if is_admin(request, settings) else "public",
        access_required=settings.access_required,
        llm_mode="demo" if provider == "demo" else "live",
        provider=provider,
        configured_provider=settings.llm_provider,
        model=settings.model_id,
        key_present=settings.key_present,
        index_loaded=bool(idx["index_loaded"]),
        chunks=int(idx["chunks"]),
        source_pages=int(idx["source_pages"]),
        counts=Counts(cases=n_cases, drugs=n_drugs, runs=n_runs),
        benchmark=bench,
        database=db,
        data_errors=errors,
        warnings=warnings,
    )
