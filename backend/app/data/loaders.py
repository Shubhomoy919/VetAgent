"""Load and validate the benchmark data.

The case set and drug table live in the database (tables `cases` and `drug_rows`). data/cases.json and
data/drug_table.csv are the seed files: `python -m app.scripts.seed` validates them and loads them.
Errors are raised as DataError with a message that names the source, the record and the failing field, so the
UI can show the real problem.
"""

import csv
import json
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import DATA_DIR
from app.data.models import Case, DrugRow

CASES_PATH = DATA_DIR / "cases.json"
DRUGS_PATH = DATA_DIR / "drug_table.csv"

DRUG_COLUMNS = [
    "species",
    "drug",
    "status",
    "dose_min_mg_per_kg",
    "dose_max_mg_per_kg",
    "milk_withdrawal_days",
    "meat_withdrawal_days",
    "legal_in_india",
    "source",
    "notes",
    "verified_by",
    "verified_on",
]


class DataError(Exception):
    """A data file is missing, unreadable or fails validation."""


def _format_validation(err: ValidationError) -> str:
    parts = []
    for e in err.errors():
        loc = ".".join(str(x) for x in e["loc"]) or "(record)"
        parts.append(f"{loc}: {e['msg']}")
    return "; ".join(parts)


def read_cases_file(path: Path | None = None) -> list[Case]:
    """Validate a cases JSON file (the seed file by default)."""
    path = path or CASES_PATH
    if not path.is_file():
        raise DataError(f"{path.name} not found at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise DataError(f"{path.name} is not valid JSON: {e}") from e
    if not isinstance(raw, list):
        raise DataError(f"{path.name} must contain a JSON list of cases")

    cases: list[Case] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        label = item.get("case_id", f"#{i}") if isinstance(item, dict) else f"#{i}"
        try:
            case = Case.model_validate(item)
        except ValidationError as e:
            raise DataError(f"{path.name} case {label}: {_format_validation(e)}") from e
        if case.case_id in seen:
            raise DataError(f"{path.name}: duplicate case_id {case.case_id}")
        seen.add(case.case_id)
        cases.append(case)
    return cases


def read_drugs_file(path: Path | None = None) -> list[DrugRow]:
    """Validate a drug-table CSV file (the seed file by default)."""
    path = path or DRUGS_PATH
    if not path.is_file():
        raise DataError(f"{path.name} not found at {path}")
    try:
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in DRUG_COLUMNS if c not in header]
            if missing:
                raise DataError(f"{path.name} is missing columns: {', '.join(missing)}")
            rows_raw = list(reader)
    except (OSError, csv.Error) as e:
        raise DataError(f"{path.name} could not be read: {e}") from e

    rows: list[DrugRow] = []
    seen: set[tuple[str, str]] = set()
    for line_no, raw in enumerate(rows_raw, start=2):  # header is line 1
        try:
            row = DrugRow.model_validate(raw)
        except ValidationError as e:
            raise DataError(f"{path.name} line {line_no}: {_format_validation(e)}") from e
        key = (row.species, row.drug.lower())
        if key in seen:
            raise DataError(f"{path.name} line {line_no}: duplicate row for {row.species}/{row.drug}")
        seen.add(key)
        rows.append(row)
    return rows


# ---------- from the database ----------

_cache_lock = threading.Lock()
_cache: dict[tuple[str, str, str], list[Any]] = {}


def _from_db(kind: str) -> list[Any]:
    from app.storage.db import get_store

    try:
        store = get_store()
        rev = store.data_rev()
        key = (store.url, kind, rev)
        with _cache_lock:
            if key in _cache:
                return list(_cache[key])
        records = store.case_records() if kind == "cases" else store.drug_records()
    except Exception as e:  # database unreachable or not migrated
        raise DataError(f"Benchmark data could not be read from the database ({type(e).__name__})") from e
    if not records:
        raise DataError(f"No {'cases' if kind == 'cases' else 'drug rows'} in the database. Run: python -m app.scripts.seed")
    model = Case if kind == "cases" else DrugRow
    out = []
    for rec in records:
        try:
            out.append(model.model_validate({k: v for k, v in rec.items() if k != "verified"}))
        except ValidationError as e:
            label = rec.get("case_id") or f"{rec.get('species')}/{rec.get('drug')}"
            raise DataError(f"Stored {kind} record {label}: {_format_validation(e)}") from e
    with _cache_lock:
        if len(_cache) > 8:
            _cache.clear()
        _cache[key] = out
    return list(out)


def load_cases(path: Path | None = None) -> list[Case]:
    """The current case set (from the database; from a file when `path` is given)."""
    return read_cases_file(path) if path else _from_db("cases")


def load_drugs(path: Path | None = None) -> list[DrugRow]:
    """The current drug table (from the database; from a file when `path` is given)."""
    return read_drugs_file(path) if path else _from_db("drugs")
