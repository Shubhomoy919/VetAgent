"""Editing cases and drug rows through the API, against temp copies of the real data files."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import DATA_DIR
from app.data import loaders
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch):
    cases = tmp_path / "cases.json"
    drugs = tmp_path / "drug_table.csv"
    shutil.copy(DATA_DIR / "cases.json", cases)
    shutil.copy(DATA_DIR / "drug_table.csv", drugs)
    monkeypatch.setattr(loaders, "CASES_PATH", cases)
    monkeypatch.setattr(loaders, "DRUGS_PATH", drugs)
    return TestClient(app)


def get_case(c: TestClient, cid: str) -> dict:
    return c.get(f"/api/cases/{cid}").json()


# ---------- cases ----------

def test_update_case_persists(client):
    case = get_case(client, "BOV-WD-007")
    case["history"] = "Edited history."
    r = client.put("/api/cases/BOV-WD-007", json=case)
    assert r.status_code == 200
    assert loaders.load_cases()[[c.case_id for c in loaders.load_cases()].index("BOV-WD-007")].history == "Edited history."


def test_invalid_weight_rejected_and_file_unchanged(client):
    before = loaders.CASES_PATH.read_text(encoding="utf-8")
    case = get_case(client, "BOV-WD-007")
    case["signalment"]["weight_kg"] = 90
    r = client.put("/api/cases/BOV-WD-007", json=case)
    assert r.status_code == 422
    body = r.json()
    assert body["detail"] == "Case failed validation"
    assert any("outside the cattle range" in e["msg"] for e in body["errors"])
    assert loaders.CASES_PATH.read_text(encoding="utf-8") == before


def test_field_level_error_location(client):
    case = get_case(client, "BOV-001")
    case["signalment"]["age_months"] = -3
    errors = client.put("/api/cases/BOV-001", json=case).json()["errors"]
    assert ["signalment", "age_months"] in [e["loc"] for e in errors]


def test_prefix_species_mismatch(client):
    case = get_case(client, "BOV-001")
    case["case_id"] = "CAP-777"
    r = client.put("/api/cases/BOV-001", json=case)
    assert r.status_code == 422
    assert any("prefix CAP" in e["msg"] for e in r.json()["errors"])


def test_rename_to_existing_id_rejected(client):
    case = get_case(client, "BOV-001")
    case["case_id"] = "BOV-002"
    r = client.put("/api/cases/BOV-001", json=case)
    assert r.status_code == 422
    assert "already exists" in r.json()["errors"][0]["msg"]


def test_rename_case(client):
    case = get_case(client, "BOV-001")
    case["case_id"] = "BOV-101"
    assert client.put("/api/cases/BOV-001", json=case).status_code == 200
    ids = [c.case_id for c in loaders.load_cases()]
    assert "BOV-101" in ids and "BOV-001" not in ids
    assert ids.index("BOV-101") == 0  # position kept


def test_create_and_delete_case(client):
    new = get_case(client, "CAP-005")
    new["case_id"] = "CAP-099"
    new["signalment"]["weight_kg"] = 33
    assert client.post("/api/cases", json=new).status_code == 201
    assert client.post("/api/cases", json=new).status_code == 422  # duplicate
    assert client.delete("/api/cases/CAP-099").status_code == 204
    assert client.delete("/api/cases/CAP-099").status_code == 404
    assert client.put("/api/cases/NOPE-001", json=new).status_code == 404


def test_save_roundtrip_keeps_data(client):
    before = [c.model_dump() for c in loaders.load_cases()]
    case = get_case(client, "AVI-001")
    assert client.put("/api/cases/AVI-001", json=case).status_code == 200
    assert [c.model_dump() for c in loaders.load_cases()] == before


def test_export_and_import_cases(client):
    exported = client.get("/api/cases/export")
    assert exported.headers["content-disposition"].endswith('filename="cases.json"')
    body = exported.json()
    assert body["meta"]["benchmark_version"].startswith("1.0.0") and "not for clinical use" in body["meta"]["disclaimer"]
    items = body["cases"]
    assert len(items) >= 25

    items[0]["history"] = "Imported change."
    r = client.post("/api/cases/import", params={"mode": "merge"}, json=items[:1])
    assert r.status_code == 200 and r.json()["imported"] == 1 and r.json()["total"] == len(items)
    assert loaders.load_cases()[0].history == "Imported change."

    r = client.post("/api/cases/import", params={"mode": "replace"}, json=items[:3])
    assert r.json()["total"] == 3 and len(loaders.load_cases()) == 3


def test_import_is_all_or_nothing(client):
    items = client.get("/api/cases/export").json()["cases"]
    before = loaders.CASES_PATH.read_text(encoding="utf-8")
    items[1]["signalment"]["weight_kg"] = 9999
    r = client.post("/api/cases/import", params={"mode": "replace"}, json=items)
    assert r.status_code == 422
    assert "nothing was imported" in r.json()["detail"]
    assert r.json()["errors"][0]["loc"][0] == items[1]["case_id"]
    assert loaders.CASES_PATH.read_text(encoding="utf-8") == before


def test_import_bad_shape(client):
    assert client.post("/api/cases/import", json={"not": "a list"}).status_code == 400
    assert client.post("/api/cases/import", params={"mode": "wipe"}, json=[]).status_code == 400


# ---------- drug table ----------

def drug(c: TestClient, species: str, name: str) -> dict:
    return next(d for d in c.get("/api/drugs").json() if d["species"] == species and d["drug"] == name)


def test_update_drug_row(client):
    row = drug(client, "cattle", "meloxicam")
    row["notes"] = "edited"
    r = client.put("/api/drugs", params={"key": "cattle|meloxicam"}, json=row)
    assert r.status_code == 200
    assert drug(client, "cattle", "meloxicam")["notes"] == "edited"


def test_banned_drug_with_dose_rejected(client):
    row = drug(client, "cattle", "diclofenac")
    row["dose_min_mg_per_kg"] = 1
    row["dose_max_mg_per_kg"] = 2
    r = client.put("/api/drugs", params={"key": "cattle|diclofenac"}, json=row)
    assert r.status_code == 422
    assert any("must not carry a dose" in e["msg"] for e in r.json()["errors"])


def test_drug_number_field_error(client):
    row = drug(client, "goat", "albendazole")
    row["dose_min_mg_per_kg"] = "lots"
    errors = client.put("/api/drugs", params={"key": "goat|albendazole"}, json=row).json()["errors"]
    assert ["dose_min_mg_per_kg"] in [e["loc"] for e in errors]


def test_create_duplicate_delete_drug(client):
    row = {"species": "goat", "drug": "fenbendazole", "status": "safe", "dose_min_mg_per_kg": 5,
           "dose_max_mg_per_kg": 10, "milk_withdrawal_days": None, "meat_withdrawal_days": None,
           "legal_in_india": True, "source": "SVTG 2024 Annexure-7, PDF p.400", "notes": "",
           "verified_by": "", "verified_on": ""}
    assert client.post("/api/drugs", json=row).status_code == 201
    assert client.post("/api/drugs", json=row).status_code == 422
    assert client.delete("/api/drugs", params={"key": "goat|fenbendazole"}).status_code == 204
    assert client.delete("/api/drugs", params={"key": "goat|fenbendazole"}).status_code == 404


def test_mark_verified_needs_name_and_date(client):
    row = drug(client, "cat", "paracetamol")
    row["verified_by"] = "Dr. A"
    r = client.put("/api/drugs", params={"key": "cat|paracetamol"}, json=row)
    assert r.status_code == 422
    row["verified_on"] = "2026-10-03"
    r = client.put("/api/drugs", params={"key": "cat|paracetamol"}, json=row)
    assert r.status_code == 200 and r.json()["verified"] is True


def test_drug_csv_export_import_roundtrip(client):
    before = [d.model_dump() for d in loaders.load_drugs()]
    csv_text = client.get("/api/drugs/export").text
    r = client.post("/api/drugs/import", params={"mode": "replace"}, content=csv_text.encode("utf-8"),
                    headers={"Content-Type": "text/csv"})
    assert r.status_code == 200 and r.json()["total"] == len(before)
    assert [d.model_dump() for d in loaders.load_drugs()] == before


def test_drug_import_errors(client):
    bad = "species,drug\ncat,x\n"
    r = client.post("/api/drugs/import", content=bad.encode(), headers={"Content-Type": "text/csv"})
    assert r.status_code == 400 and "missing columns" in r.json()["detail"]
    header = ",".join(loaders.DRUG_COLUMNS)
    rows = header + "\ncattle,x,safe,5,1,,,true,s,,,\n"
    r = client.post("/api/drugs/import", content=rows.encode(), headers={"Content-Type": "text/csv"})
    assert r.status_code == 422 and r.json()["errors"][0]["loc"][0] == "line 2"


def test_validation_meta(client):
    meta = client.get("/api/meta/validation").json()
    assert meta["weight_ranges"]["dog"] == [[3, 15], [20, 45]]
    assert meta["prefix_species"]["BOV"] == ["cattle", "buffalo"]
    assert "withdrawal_legal" in meta["question_types"]


def test_real_files_untouched_by_tests():
    # The fixture redirects writes; the committed data must still load cleanly.
    assert len(json.loads((DATA_DIR / "cases.json").read_text(encoding="utf-8"))) >= 25
