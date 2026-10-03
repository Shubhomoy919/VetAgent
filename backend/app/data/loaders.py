"""Load and validate data/cases.json and data/drug_table.csv.

Errors are raised as DataError with a message that names the file, the record
and the failing field, so the UI can show the real problem.
"""

import csv
import json
from pathlib import Path

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


def load_cases(path: Path | None = None) -> list[Case]:
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


def load_drugs(path: Path | None = None) -> list[DrugRow]:
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
