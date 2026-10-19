"""Seed script (safe to run twice), migrations matching the schema, and the benchmark hash from the database."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete

from app.config import Settings
from app.data.benchmark import benchmark_info, file_benchmark_info
from app.scripts import seed
from app.storage import schema as t

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = Settings(_env_file=None).snapshot_file


def empty(store) -> None:
    with store._tx() as c:
        for table in reversed(t.metadata.sorted_tables):
            c.execute(delete(table))


def test_seed_is_safe_to_run_twice(_isolated, tmp_path):
    store = _isolated
    empty(store)
    assert seed.seed_data(store, reset=False) == "loaded 29 cases and 31 drug rows"
    assert seed.seed_data(store, reset=False).startswith("already loaded")
    first = seed.seed_snapshot(store, SNAPSHOT)
    assert first.startswith("loaded run 20261019-090352-249aa9")
    assert seed.seed_snapshot(store, SNAPSHOT) == "run already present; 0 answer(s) added to the cache"
    assert store.count_runs() == 1 and len(store.results("20261019-090352-249aa9")) == 145
    missing = seed.seed_svtg(store, tmp_path / "missing.pdf")
    assert missing.startswith("SKIPPED: no PDF") and "index_loaded: false" in missing
    assert store.chunk_count() == 0


def test_seeded_database_has_the_frozen_benchmark_hash(_isolated):
    b, f = benchmark_info(), file_benchmark_info()
    assert b["hash"] == f["hash"] == "b4b15a6930708f0976cb2b119f389c6d32ac321f8e2715d1751fed7c721edf07"
    assert b["frozen"] is True and b["version"] == "1.0.0"


def test_edits_are_kept_unless_reset(_isolated):
    store = _isolated
    cases = store.case_records()
    cases[0] = {**cases[0], "history": cases[0]["history"] + " Edited."}
    store.replace_cases(cases)
    assert benchmark_info()["version"] == "1.0.0+modified"
    assert seed.seed_data(store, reset=False).startswith("kept: the database differs")
    assert seed.seed_data(store, reset=True).startswith("replaced with the seed files")
    assert benchmark_info()["frozen"] is True


def test_snapshot_answers_seed_the_cache(_isolated):
    """Re-running a frozen case with the snapshot's model, prompt (v2) and settings hits the cache: no tokens."""
    from app.agent.runner import cache_key
    from app.data.loaders import load_cases

    seed.seed_snapshot(_isolated, SNAPSHOT)
    case = next(c for c in load_cases() if c.case_id == "BOV-WD-007")
    live = type("Live", (), {"name": "gemini", "model": "gemini-3.5-flash-lite"})()
    key = cache_key(live, "C4", case, False, Settings(_env_file=None))  # type: ignore[arg-type]
    hit = _isolated.cache_get(key)
    assert hit is not None and hit["status"] == "ok" and hit["answer"]["most_likely"]


def test_seed_svtg_from_pdf_once(_isolated):
    pdf = REPO_ROOT / "data" / "StandardVeterinaryTreatment.pdf"
    if not pdf.is_file():
        pytest.skip("SVTG PDF not present")
    out = seed.seed_svtg(_isolated, pdf)
    assert out.startswith("loaded ") and "passages from" in out
    assert _isolated.chunk_count() > 1000 and _isolated.svtg_source()["pages"] > 300
    assert seed.seed_svtg(_isolated, pdf).startswith("already loaded")


def test_migrations_match_the_schema(tmp_path):
    """`alembic upgrade head` on an empty database gives exactly the tables and columns in schema.py."""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.config import Config
    from alembic.migration import MigrationContext

    url = f"sqlite:///{(tmp_path / 'migrated.db').as_posix()}"
    cfg = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), t.metadata)
    engine.dispose()
    assert diff == []
