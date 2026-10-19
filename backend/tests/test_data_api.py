from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_cases():
    res = client.get("/api/cases")
    assert res.status_code == 200
    cases = res.json()
    assert len(cases) >= 25
    first = cases[0]
    for field in ("case_id", "species", "signalment", "question_type", "gold_answer", "vet_verified"):
        assert field in first


def test_get_case_and_404():
    res = client.get("/api/cases/BOV-WD-007")
    assert res.status_code == 200
    assert res.json()["species"] == "cattle"
    missing = client.get("/api/cases/BOV-999")
    assert missing.status_code == 404
    assert "BOV-999" in missing.json()["detail"]


def test_list_drugs_marks_unverified():
    rows = client.get("/api/drugs").json()
    assert len(rows) >= 25
    assert all(r["verified"] is False for r in rows)
    banned = {r["drug"] for r in rows if r["status"] == "banned_in_india"}
    assert {"diclofenac", "ketoprofen", "aceclofenac"} <= banned


def test_search_returns_pages(svtg):
    res = client.get("/api/search", params={"q": "buparvaquone milk withdrawal", "k": 3})
    assert res.status_code == 200
    body = res.json()
    assert body["total_chunks"] > 1000
    assert body["passages"][0]["page"] == 175
    assert body["passages"][0]["printed_page"] == 157


def test_search_validates_query():
    assert client.get("/api/search", params={"q": ""}).status_code == 422


def test_health_counts_real_data(svtg):
    body = client.get("/api/health").json()
    assert body["counts"]["cases"] >= 25
    assert body["counts"]["drugs"] >= 25
    assert body["chunks"] > 1000
    assert body["index_loaded"] is True and body["source_pages"] > 300
    assert body["data_errors"] == [] and body["warnings"] == []


def test_case_dose_band_is_computed_from_the_drug_table():
    d = client.get("/api/cases/BOV-WD-007/dose").json()
    assert d["drug"] == "buparvaquone" and d["status"] == "safe"
    # 2.5 mg/kg (drug table) x 410 kg (case) — computed in Python, not invented
    assert d["dose_mg_total"] == {"min": 1025.0, "max": 1025.0, "weight_kg": 410.0}


def test_case_dose_banned_and_no_drug():
    d = client.get("/api/cases/BOV-008/dose").json()
    assert d["status"] == "banned_in_india" and "dose_mg_total" not in d
    no_drug = client.get("/api/cases/BOV-001/dose").json()
    assert no_drug["drug"] is None
    assert client.get("/api/cases/NOPE-1/dose").status_code == 404
