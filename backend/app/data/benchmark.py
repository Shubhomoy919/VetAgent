"""Benchmark version and content hash.

The hash covers the validated case set and drug table, serialised canonically (sorted keys, no whitespace), so
reformatting does not change it but any change to content does. The same hash is computed for the data in the
database (what the app serves) and for the seed files. `benchmark.json` (shipped with the code) records the
frozen v1.0 hashes; if the data no longer matches, the version reads "1.0.0+modified".
"""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.data import loaders
from app.data.models import Case, DrugRow

MANIFEST_PATH = Path(__file__).with_name("benchmark.json")
DISCLAIMER = "Research prototype, not for clinical use. Consult a registered veterinarian."


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def cases_hash(cases: list[Case]) -> str:
    return _sha(sorted((c.model_dump(mode="json") for c in cases), key=lambda d: d["case_id"]))


def drugs_hash(drugs: list[DrugRow]) -> str:
    rows = [d.model_dump(mode="json", exclude={"verified"}) for d in drugs]
    return _sha(sorted(rows, key=lambda d: (d["species"], d["drug"].lower())))


def combined_hash(c_hash: str, d_hash: str) -> str:
    return hashlib.sha256(f"cases:{c_hash}\ndrugs:{d_hash}\n".encode()).hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def info_for(cases: list[Case], drugs: list[DrugRow]) -> dict[str, Any]:
    c_hash, d_hash = cases_hash(cases), drugs_hash(drugs)
    full = combined_hash(c_hash, d_hash)
    manifest = load_manifest()
    frozen = full == manifest["hash"]
    return {
        "version": manifest["version"] if frozen else f"{manifest['version']}+modified",
        "frozen_version": manifest["version"],
        "frozen_on": manifest["frozen_on"],
        "hash": full,
        "short_hash": full[:12],
        "frozen": frozen,
        "cases_sha256": c_hash,
        "drugs_sha256": d_hash,
        "n_cases": len(cases),
        "n_drugs": len(drugs),
    }


@lru_cache(maxsize=8)
def _db_info(url: str, rev: str) -> dict[str, Any]:
    return info_for(loaders.load_cases(), loaders.load_drugs())


def benchmark_info() -> dict[str, Any]:
    """Version and hash of the data in the database. Raises loaders.DataError if it is missing or invalid."""
    from app.storage.db import get_store

    try:
        store = get_store()
        key = (store.url, store.data_rev())
    except Exception as e:
        raise loaders.DataError(f"Benchmark data could not be read from the database ({type(e).__name__})") from e
    return dict(_db_info(*key))


def file_benchmark_info() -> dict[str, Any]:
    """Version and hash of the seed files (data/cases.json, data/drug_table.csv)."""
    return info_for(loaders.read_cases_file(), loaders.read_drugs_file())


def export_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Provenance block written into every export."""
    try:
        b = benchmark_info()
        bench = {"benchmark_version": b["version"], "benchmark_hash": b["hash"]}
    except loaders.DataError:
        bench = {"benchmark_version": "unknown", "benchmark_hash": "unknown"}
    return {"disclaimer": DISCLAIMER, **bench, **(extra or {})}
