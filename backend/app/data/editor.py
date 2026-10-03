"""Edit cases.json and drug_table.csv safely.

Every write: validate each record with the Pydantic model, check uniqueness across the whole file,
then write to a temp file and atomically replace the original. Validation failures raise EditError
with a list of {loc, msg} items so the UI can point at the field.
"""

import csv
import io
import json
import os
import threading
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.data import loaders
from app.data.models import Case, DrugRow

_lock = threading.Lock()


class EditError(Exception):
    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None, status: int = 422):
        super().__init__(message)
        self.message = message
        self.errors = errors or []
        self.status = status


def _errors(err: ValidationError, prefix: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [{"loc": [*prefix, *e["loc"]], "msg": e["msg"].removeprefix("Value error, ")} for e in err.errors()]


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    os.replace(tmp, path)


def drug_key(row: DrugRow) -> str:
    return f"{row.species}|{row.drug.lower()}"


# ---------- cases ----------

def validate_case(data: dict[str, Any], prefix: tuple[Any, ...] = ()) -> Case:
    try:
        return Case.model_validate(data)
    except ValidationError as e:
        raise EditError("Case failed validation", _errors(e, prefix)) from None


def _write_cases(cases: list[Case]) -> None:
    ids = [c.case_id for c in cases]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise EditError("Duplicate case IDs", [{"loc": ["case_id"], "msg": f"case_id {d} already exists"} for d in dupes])
    text = json.dumps([c.model_dump(mode="json") for c in cases], indent=2, ensure_ascii=False) + "\n"
    _atomic_write(loaders.CASES_PATH, text)


def save_case(data: dict[str, Any], original_id: str | None) -> Case:
    """Create (original_id None) or update the case with original_id (its ID may change)."""
    case = validate_case(data)
    with _lock:
        cases = loaders.load_cases()
        if original_id is None:
            if any(c.case_id == case.case_id for c in cases):
                raise EditError("Duplicate case ID", [{"loc": ["case_id"], "msg": f"case_id {case.case_id} already exists"}])
            cases.append(case)
        else:
            idx = next((i for i, c in enumerate(cases) if c.case_id == original_id), None)
            if idx is None:
                raise EditError(f"No case {original_id}", status=404)
            if case.case_id != original_id and any(c.case_id == case.case_id for c in cases):
                raise EditError("Duplicate case ID", [{"loc": ["case_id"], "msg": f"case_id {case.case_id} already exists"}])
            cases[idx] = case
        _write_cases(cases)
    return case


def delete_case(case_id: str) -> None:
    with _lock:
        cases = loaders.load_cases()
        kept = [c for c in cases if c.case_id != case_id]
        if len(kept) == len(cases):
            raise EditError(f"No case {case_id}", status=404)
        _write_cases(kept)


def import_cases(items: Any, mode: str) -> dict[str, Any]:
    """mode 'merge' upserts by case_id; 'replace' replaces the whole file. All-or-nothing."""
    if mode not in ("merge", "replace"):
        raise EditError("mode must be 'merge' or 'replace'", status=400)
    if not isinstance(items, list):
        raise EditError("Import must be a JSON list of cases", status=400)
    errors: list[dict[str, Any]] = []
    parsed: list[Case] = []
    for i, item in enumerate(items):
        label = item.get("case_id", f"#{i}") if isinstance(item, dict) else f"#{i}"
        try:
            parsed.append(Case.model_validate(item))
        except ValidationError as e:
            errors.extend(_errors(e, (label,)))
    if errors:
        raise EditError(f"{len(errors)} validation error(s); nothing was imported", errors)
    with _lock:
        if mode == "replace":
            result = parsed
        else:
            result = loaders.load_cases()
            pos = {c.case_id: i for i, c in enumerate(result)}
            for c in parsed:
                if c.case_id in pos:
                    result[pos[c.case_id]] = c
                else:
                    pos[c.case_id] = len(result)
                    result.append(c)
        _write_cases(result)
    return {"imported": len(parsed), "total": len(result), "mode": mode}


def export_cases_json() -> str:
    return json.dumps([c.model_dump(mode="json") for c in loaders.load_cases()], indent=2, ensure_ascii=False)


# ---------- drug table ----------

def validate_drug(data: dict[str, Any], prefix: tuple[Any, ...] = ()) -> DrugRow:
    clean = {k: v for k, v in data.items() if k != "verified"}
    try:
        return DrugRow.model_validate(clean)
    except ValidationError as e:
        raise EditError("Drug row failed validation", _errors(e, prefix)) from None


def drugs_csv(rows: list[DrugRow]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(loaders.DRUG_COLUMNS)
    for r in rows:
        d = r.model_dump()
        out = []
        for col in loaders.DRUG_COLUMNS:
            v = d[col]
            if v is None:
                out.append("")
            elif isinstance(v, bool):
                out.append("true" if v else "false")
            elif isinstance(v, float) and v.is_integer():
                out.append(str(int(v)))
            else:
                out.append(str(v))
        w.writerow(out)
    return buf.getvalue()


def _write_drugs(rows: list[DrugRow]) -> None:
    keys = [drug_key(r) for r in rows]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise EditError("Duplicate drug rows", [{"loc": ["drug"], "msg": f"{d.replace('|', ' / ')} already exists"} for d in dupes])
    _atomic_write(loaders.DRUGS_PATH, drugs_csv(rows))


def save_drug(data: dict[str, Any], original_key: str | None) -> DrugRow:
    row = validate_drug(data)
    with _lock:
        rows = loaders.load_drugs()
        if original_key is None:
            if any(drug_key(r) == drug_key(row) for r in rows):
                raise EditError("Duplicate drug row", [{"loc": ["drug"], "msg": f"{row.species} / {row.drug} already exists"}])
            rows.append(row)
        else:
            idx = next((i for i, r in enumerate(rows) if drug_key(r) == original_key.lower()), None)
            if idx is None:
                raise EditError(f"No drug row {original_key}", status=404)
            if drug_key(row) != original_key.lower() and any(drug_key(r) == drug_key(row) for r in rows):
                raise EditError("Duplicate drug row", [{"loc": ["drug"], "msg": f"{row.species} / {row.drug} already exists"}])
            rows[idx] = row
        _write_drugs(rows)
    return row


def delete_drug(key: str) -> None:
    with _lock:
        rows = loaders.load_drugs()
        kept = [r for r in rows if drug_key(r) != key.lower()]
        if len(kept) == len(rows):
            raise EditError(f"No drug row {key}", status=404)
        _write_drugs(kept)


def import_drugs_csv(text: str, mode: str) -> dict[str, Any]:
    if mode not in ("merge", "replace"):
        raise EditError("mode must be 'merge' or 'replace'", status=400)
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in loaders.DRUG_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise EditError(f"CSV is missing columns: {', '.join(missing)}", status=400)
    errors: list[dict[str, Any]] = []
    parsed: list[DrugRow] = []
    for line_no, raw in enumerate(reader, start=2):
        try:
            parsed.append(DrugRow.model_validate({k: raw.get(k, "") for k in loaders.DRUG_COLUMNS}))
        except ValidationError as e:
            errors.extend(_errors(e, (f"line {line_no}",)))
    if errors:
        raise EditError(f"{len(errors)} validation error(s); nothing was imported", errors)
    with _lock:
        if mode == "replace":
            result = parsed
        else:
            result = loaders.load_drugs()
            pos = {drug_key(r): i for i, r in enumerate(result)}
            for r in parsed:
                k = drug_key(r)
                if k in pos:
                    result[pos[k]] = r
                else:
                    pos[k] = len(result)
                    result.append(r)
        _write_drugs(result)
    return {"imported": len(parsed), "total": len(result), "mode": mode}
