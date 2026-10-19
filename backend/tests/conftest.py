"""Keep tests hermetic: never read the developer's .env, and give every test a clean database.

Without this, a real API key in .env would switch tests to live mode and spend quota.

The database is a SQLite file per session, or Postgres when TEST_DATABASE_URL is set (CI). Postgres is set up
with the Alembic migrations, so the tests also prove the migrations match the schema. Before each test every
table is emptied and the seed cases and drug rows are loaded.
"""

import os
from functools import lru_cache
from pathlib import Path

import pytest
from sqlalchemy import delete

from app import config
from app.data import benchmark, loaders
from app.storage import db as db_mod
from app.storage import schema as t

REPO_ROOT = Path(__file__).resolve().parents[2]
PDF = REPO_ROOT / "data" / "StandardVeterinaryTreatment.pdf"

ENV_VARS = ("LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_MODEL", "OPENAI_MODEL",
            "APP_ENV", "ADMIN_ACCESS_CODE", "SESSION_SECRET", "ALLOWED_ORIGINS", "RATE_LIMIT_PER_MINUTE",
            "MAX_DAILY_TOKENS", "MAX_CASES_PER_RUN", "MAX_BODY_BYTES", "DATABASE_URL_UNPOOLED", "STEP_DEADLINE_S",
            "VERCEL")


@pytest.fixture(scope="session")
def database_url(tmp_path_factory) -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if url:
        from alembic import command
        from alembic.config import Config

        url = db_mod.normalize_url(url)
        cfg = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
        cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()  # same as: alembic -x url=... upgrade head
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        return url
    return f"sqlite:///{(tmp_path_factory.mktemp('db') / 'test.db').as_posix()}"


@lru_cache(maxsize=1)
def seed_records() -> tuple[list[dict], list[dict]]:
    cases = [c.model_dump(mode="json") for c in loaders.read_cases_file()]
    drugs = [d.model_dump(mode="json", exclude={"verified"}) for d in loaders.read_drugs_file()]
    return cases, drugs


def reset_caches() -> None:
    config.reset_settings_cache()
    db_mod.reset_store_cache()
    loaders._cache.clear()
    benchmark._db_info.cache_clear()
    from app.retrieval import service

    service._cache.clear()


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, database_url):
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)
    reset_caches()
    store = db_mod.get_store()
    with store._tx() as c:
        for table in reversed(t.metadata.sorted_tables):
            c.execute(delete(table))
    cases, drugs = seed_records()
    store.replace_cases(cases)
    store.replace_drugs(drugs)
    yield store
    reset_caches()


@lru_cache(maxsize=1)
def _pdf_chunks() -> list[dict]:
    from app.retrieval.ingest import build_chunks

    return [{"chunk_id": c.chunk_id, "page": c.page, "printed_page": c.printed_page, "section": c.section,
             "text": c.text} for c in build_chunks(PDF)]


def load_svtg(store) -> None:
    """Store the SVTG passages from the local PDF (tests that need it skip when the PDF is absent)."""
    from app.retrieval.ingest import page_count

    store.replace_chunks(_pdf_chunks(), {"title": "SVTG", "file": PDF.name, "pages": page_count(PDF), "index_version": 0})


@pytest.fixture
def svtg(_isolated):
    if not PDF.is_file():
        pytest.skip("SVTG PDF not present")
    load_svtg(_isolated)
    return _isolated


FAKE_PASSAGES = [
    {"chunk_id": "p175-c1", "page": 175, "printed_page": 157, "section": "5.2 Theileriosis",
     "text": "Buparvaquone 2.5 mg/kg body weight by deep intramuscular injection is the drug of choice for "
             "tropical theileriosis in cattle and buffalo."},
    {"chunk_id": "p110-c1", "page": 110, "printed_page": 92, "section": "3.1 Rabies",
     "text": "Rabies is a fatal zoonotic disease. Suspected cases must be isolated and reported."},
    {"chunk_id": "p401-c1", "page": 401, "printed_page": 383, "section": "Annexure-7 Drugs usage in ruminants",
     "text": "Ketoprofen LA 2-4 mg/kg. Meloxicam 0.5 mg/kg."},
]


@pytest.fixture
def fake_svtg(_isolated):
    """Three made-up passages in the SVTG format, so the database-backed index is tested without the PDF."""
    _isolated.replace_chunks(FAKE_PASSAGES, {"title": "SVTG (test passages)", "file": "test.pdf", "pages": 406,
                                             "index_version": 0})
    return _isolated
