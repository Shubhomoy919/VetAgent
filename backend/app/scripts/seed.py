"""Load the benchmark data, the frozen v1.0.0 results and the SVTG passages into the database. Safe to run twice.

    python -m app.scripts.seed                 # cases, drug table, snapshot, answer cache, SVTG passages
    python -m app.scripts.seed --skip-svtg     # everything except the SVTG passages
    python -m app.scripts.seed --reset-data    # overwrite cases and drug rows edited in the app with the seed files

Database: DATABASE_URL_UNPOOLED if set (a direct connection, for Neon), else DATABASE_URL, else the local SQLite
file. On Postgres, run `alembic upgrade head` first. The SVTG PDF is read from SVTG_PDF_PATH on this machine;
only page-numbered passages are stored, the PDF itself is never uploaded or deployed.
"""

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def _use_unpooled() -> None:
    """Point this process at the direct connection before anything opens the database."""
    from app.config import env_settings, reset_settings_cache

    unpooled = env_settings().database_url_unpooled
    if unpooled:
        os.environ["DATABASE_URL"] = unpooled
        reset_settings_cache()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def seed_data(store, reset: bool) -> str:
    from app.data import loaders

    cases = [c.model_dump(mode="json") for c in loaders.read_cases_file()]
    drugs = [d.model_dump(mode="json", exclude={"verified"}) for d in loaders.read_drugs_file()]
    have_cases, have_drugs = store.case_records(), store.drug_records()
    if not have_cases and not have_drugs:
        store.replace_cases(cases)
        store.replace_drugs(drugs)
        return f"loaded {len(cases)} cases and {len(drugs)} drug rows"
    if have_cases == cases and have_drugs == drugs:
        return f"already loaded ({len(cases)} cases, {len(drugs)} drug rows)"
    if reset:
        store.replace_cases(cases)
        store.replace_drugs(drugs)
        return f"replaced with the seed files ({len(cases)} cases, {len(drugs)} drug rows)"
    return (f"kept: the database differs from the seed files ({len(have_cases)} cases, {len(have_drugs)} drug rows, "
            "edited in the app). Use --reset-data to overwrite")


def seed_snapshot(store, path: Path) -> str:
    from app.snapshot import load_snapshot, seed_cache_from_snapshot

    rid = load_snapshot(store, path)
    added = seed_cache_from_snapshot(store, path)
    run = f"loaded run {rid}" if rid else "run already present"
    return f"{run}; {added} answer(s) added to the cache"


def seed_svtg(store, pdf: Path) -> str:
    from app.retrieval.ingest import INDEX_VERSION, build_chunks, page_count

    if not pdf.is_file():
        return (f"SKIPPED: no PDF at {pdf}. Download DAHD's copy and set SVTG_PDF_PATH. "
                "Until then /api/health reports index_loaded: false")
    digest = _sha256(pdf)
    source = store.svtg_source() or {}
    if source.get("sha256") == digest and source.get("index_version") == INDEX_VERSION and store.chunk_count():
        return f"already loaded ({store.chunk_count()} passages from {source.get('pages')} pages)"
    chunks = build_chunks(pdf)
    meta = {
        "title": "Standard Veterinary Treatment Guidelines (SVTG), DAHD, Government of India",
        "file": pdf.name, "sha256": digest, "pages": page_count(pdf), "index_version": INDEX_VERSION,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    store.replace_chunks([{"chunk_id": c.chunk_id, "page": c.page, "printed_page": c.printed_page,
                           "section": c.section, "text": c.text} for c in chunks], meta)
    return f"loaded {len(chunks)} passages from {meta['pages']} pages ({pdf.name})"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", type=Path, default=None, help="SVTG PDF (default SVTG_PDF_PATH)")
    ap.add_argument("--skip-svtg", action="store_true", help="do not load SVTG passages")
    ap.add_argument("--reset-data", action="store_true", help="overwrite cases and drug rows with the seed files")
    args = ap.parse_args(argv)

    _use_unpooled()
    from sqlalchemy import inspect

    from app.config import get_settings
    from app.storage.db import Store, describe_url, get_store

    settings = get_settings()
    store: Store = get_store()
    if store.dialect == "postgresql" and "alembic_version" not in inspect(store.engine).get_table_names():
        print("The database has no tables yet. Run the migrations first:  alembic upgrade head", file=sys.stderr)
        return 2
    print(f"Database: {describe_url(store.url)}")
    print(f"  benchmark data : {seed_data(store, args.reset_data)}")
    if settings.snapshot_file.is_file():
        print(f"  results        : {seed_snapshot(store, settings.snapshot_file)}")
    else:
        print(f"  results        : SKIPPED, no snapshot at {settings.snapshot_path}")
    removed = Store(store.url, hide_demo=False).delete_demo_runs() if settings.is_production else 0
    if removed:
        print(f"  demo runs      : removed {removed}")
    if args.skip_svtg:
        print("  SVTG passages  : skipped (--skip-svtg)")
    else:
        print(f"  SVTG passages  : {seed_svtg(store, args.pdf or settings.pdf_path)}")

    from app.data.benchmark import benchmark_info

    b = benchmark_info()
    print(f"Benchmark {b['version']} ({b['short_hash']}), {b['n_cases']} cases, {b['n_drugs']} drug rows; "
          f"{store.count_runs()} run(s); {store.chunk_count()} SVTG passages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
