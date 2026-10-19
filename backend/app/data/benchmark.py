"""Benchmark version and content hash.

The hash covers the validated case set and drug table, serialised canonically (sorted keys, no whitespace), so
reformatting a file does not change it but any change to content does. `benchmark.json` (shipped with the
code) records the frozen v1.0 hashes; if the live data no longer matches, the version reads "1.0.0+modified".
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


@lru_cache(maxsize=8)
def _info(cases_mtime: float, drugs_mtime: float) -> dict[str, Any]:
    cases, drugs = loaders.load_cases(), loaders.load_drugs()
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


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def benchmark_info() -> dict[str, Any]:
    """Current benchmark version and hash. Raises loaders.DataError if the data files are invalid."""
    return dict(_info(_mtime(loaders.CASES_PATH), _mtime(loaders.DRUGS_PATH)))


def export_meta(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Provenance block written into every export."""
    try:
        b = benchmark_info()
        bench = {"benchmark_version": b["version"], "benchmark_hash": b["hash"]}
    except loaders.DataError:
        bench = {"benchmark_version": "unknown", "benchmark_hash": "unknown"}
    return {"disclaimer": DISCLAIMER, **bench, **(extra or {})}
