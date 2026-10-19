"""Runs list/compare, review + agreement statistics, settings (overrides, no secrets, test connection)."""

import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.scoring.stats import cohen_kappa
from app.storage.db import Store

KEY = "sk-never-show-me-123"


# ---------- Cohen's kappa ----------

def test_kappa_perfect_and_chance():
    assert cohen_kappa([(True, True), (False, False)] * 5) == pytest.approx(1.0)
    # 2x2 with po=0.5 and pe=0.5 -> 0
    assert cohen_kappa([(True, True), (True, False), (False, True), (False, False)]) == pytest.approx(0.0)


def test_kappa_known_value():
    # a=20 (yes,yes), b=5 (yes,no), c=10 (no,yes), d=15 (no,no); n=50
    pairs = [(True, True)] * 20 + [(True, False)] * 5 + [(False, True)] * 10 + [(False, False)] * 15
    po = 35 / 50
    pe = (25 / 50) * (30 / 50) + (25 / 50) * (20 / 50)
    assert cohen_kappa(pairs) == pytest.approx((po - pe) / (1 - pe))  # 0.4


def test_kappa_undefined():
    assert cohen_kappa([]) is None
    assert cohen_kappa([(True, True)] * 4) is None  # chance agreement is 1


# ---------- fixtures ----------

def ans(**kw):
    base = dict(differentials=[], most_likely="x", triage="routine", drug_status="n/a", dose_mg=None,
                withdrawal_days=None, escalate=False, zoonosis_warning=False, see_vet=True, advice="a", citations=[])
    return {**base, **kw}


def add(store: Store, run_id: str, case_id: str, cond: str, answer, status="ok", tokens=(100, 50), cost=None):
    return store.add_result(run_id, {
        "case_id": case_id, "condition": cond, "interview": False, "status": status, "answer": answer,
        "error": None if status == "ok" else "boom", "trace": [], "rules_fired": [], "owner_questions": [],
        "steps": 1, "tokens_in": tokens[0], "tokens_out": tokens[1], "cost_usd": cost, "latency_ms": 10,
        "cached": False, "cache_key": "k",
    })


class SavedSettings:
    """The saved settings (database table app_settings), seen like the old settings file."""

    def __init__(self, store: Store):
        self.store = store

    def exists(self) -> bool:
        return bool(self.store.settings_overrides())

    def read_text(self, encoding: str = "utf-8") -> str:
        return json.dumps(self.store.settings_overrides())


@pytest.fixture
def env(_isolated, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    config.reset_settings_cache()
    yield TestClient(app), _isolated, SavedSettings(_isolated)
    config.reset_settings_cache()


def two_runs(store: Store):
    a = store.create_run(provider="demo", model="demo", prompt_version="v1", conditions=["C0", "C4"],
                         case_ids=["BOV-010", "BOV-008"], interview=False)
    add(store, a, "BOV-010", "C0", ans(most_likely="nope", triage="urgent"))
    add(store, a, "BOV-008", "C0", ans(drug_status="safe"))
    add(store, a, "BOV-010", "C4", ans(most_likely="ketosis", triage="urgent"))
    add(store, a, "BOV-008", "C4", ans(drug_status="banned_in_india"), status="error")
    store.finish_run(a)
    b = store.create_run(provider="demo", model="demo", prompt_version="v1", conditions=["C0", "C4"],
                         case_ids=["BOV-010", "BOV-008"], interview=False)
    add(store, b, "BOV-010", "C0", ans(most_likely="ketosis", triage="urgent"))
    add(store, b, "BOV-008", "C0", ans(drug_status="safe"))
    add(store, b, "BOV-010", "C4", ans(most_likely="ketosis", triage="urgent"))
    add(store, b, "BOV-008", "C4", ans(drug_status="banned_in_india"))
    store.finish_run(b)
    return a, b


# ---------- runs ----------

def test_runs_list_has_totals(env):
    c, store, _ = env
    a, b = two_runs(store)
    runs = {r["id"]: r for r in c.get("/api/runs").json()}
    assert runs[a]["tokens"] == 600 and runs[a]["errors"] == 1
    assert runs[a]["cost_usd"] is None  # cost unknown on these results


def test_compare_runs(env):
    c, store, _ = env
    a, b = two_runs(store)
    body = c.get("/api/runs/compare", params={"a": a, "b": b}).json()
    assert body["conditions"] == ["C0", "C4"]
    top1 = next(m for m in body["metrics"] if m["key"] == "dx_top1")["by_condition"]["C0"]
    assert top1["a"]["rate"] == 0.0 and top1["b"]["rate"] == 0.5 and top1["delta"] == pytest.approx(0.5)
    changed = {(x["case_id"], x["condition"]) for x in body["changes"]}
    assert ("BOV-010", "C0") in changed      # dx became correct
    assert ("BOV-008", "C4") in changed      # error -> ok
    assert ("BOV-010", "C4") not in changed  # identical
    assert c.get("/api/runs/compare", params={"a": a, "b": "nope"}).status_code == 404


# ---------- review ----------

def test_review_queue_save_and_stats(env):
    c, store, _ = env
    a, b = two_runs(store)
    q = c.get("/api/review/queue", params={"run_id": b, "reviewer": "vet1"}).json()
    assert len(q["items"]) == 4 and all(i["review"] is None for i in q["items"])
    item = {(i["case_id"], i["condition"]): i for i in q["items"]}
    assert "gold_answer" not in item[("BOV-008", "C0")]["case"]
    assert item[("BOV-008", "C0")]["auto"]["dangerous"] is True

    def rate(case_id, cond, who, rating):
        rid = item[(case_id, cond)]["result_id"]
        r = c.put("/api/review", json={"result_id": rid, "reviewer": who, "rating": rating})
        assert r.status_code == 200

    # vet1 agrees with the scorer on all four
    rate("BOV-010", "C0", "vet1", "acceptable")
    rate("BOV-008", "C0", "vet1", "unacceptable")
    rate("BOV-010", "C4", "vet1", "acceptable")
    rate("BOV-008", "C4", "vet1", "acceptable")
    # vet2 disagrees once and is unsure once
    rate("BOV-010", "C0", "vet2", "unacceptable")
    rate("BOV-008", "C0", "vet2", "unacceptable")
    rate("BOV-010", "C4", "vet2", "acceptable")
    rate("BOV-008", "C4", "vet2", "unsure")
    # re-rating overwrites
    rate("BOV-010", "C4", "vet2", "acceptable")

    q2 = c.get("/api/review/queue", params={"run_id": b, "reviewer": "vet1"}).json()
    assert all(i["review"] for i in q2["items"])

    s = c.get("/api/review/stats", params={"run_id": b}).json()
    r1 = next(r for r in s["reviewers"] if r["reviewer"] == "vet1")
    assert r1["vs_auto"]["n"] == 4 and r1["vs_auto"]["percent"] == 1.0 and r1["vs_auto"]["kappa"] == pytest.approx(1.0)
    r2 = next(r for r in s["reviewers"] if r["reviewer"] == "vet2")
    assert r2["unsure"] == 1 and r2["vs_auto"]["n"] == 3 and r2["vs_auto"]["agree"] == 2
    pair = s["pairs"][0]
    assert (pair["a"], pair["b"]) == ("vet1", "vet2") and pair["n"] == 3 and pair["agree"] == 2
    assert r1["acceptable_by_condition"]["C0"]["k"] == 1 and r1["acceptable_by_condition"]["C0"]["n"] == 2


def test_review_validation(env):
    c, store, _ = env
    a, b = two_runs(store)
    rid = c.get("/api/review/queue", params={"run_id": b}).json()["items"][0]["result_id"]
    assert c.put("/api/review", json={"result_id": rid, "reviewer": "v", "rating": "great"}).status_code == 422
    assert c.put("/api/review", json={"result_id": rid, "reviewer": "", "rating": "acceptable"}).status_code == 422
    assert c.put("/api/review", json={"result_id": 99999, "reviewer": "v", "rating": "acceptable"}).status_code == 404
    c.put("/api/review", json={"result_id": rid, "reviewer": "v", "rating": "acceptable"})
    assert c.delete("/api/review", params={"result_id": rid, "reviewer": "v"}).status_code == 200
    assert c.delete("/api/review", params={"result_id": rid, "reviewer": "v"}).status_code == 404


def test_review_queue_skips_errors(env):
    c, store, _ = env
    a, _ = two_runs(store)
    items = c.get("/api/review/queue", params={"run_id": a}).json()["items"]
    assert len(items) == 3  # the error result has no answer to review


# ---------- settings ----------

def test_settings_never_expose_keys(env):
    c, _, _ = env
    r = c.get("/api/settings")
    assert r.status_code == 200
    assert KEY not in r.text
    assert "gemini_api_key" not in r.json()["values"]
    assert set(config.EDITABLE_FIELDS).isdisjoint({"gemini_api_key", "openai_api_key"})


def test_settings_reject_keys_and_bad_values(env):
    c, _, overrides = env
    r = c.put("/api/settings", json={"gemini_api_key": "x"})
    assert r.status_code == 422 and "not editable" in r.json()["errors"][0]["msg"]
    r = c.put("/api/settings", json={"temperature": 3})
    assert r.status_code == 422 and r.json()["errors"][0]["loc"] == ["temperature"]
    r = c.put("/api/settings", json={"svtg_pdf_path": "data/missing.pdf"})
    assert r.status_code == 422 and r.json()["errors"][0]["loc"] == ["svtg_pdf_path"]
    assert not overrides.exists()


def test_settings_save_without_pdf(env, monkeypatch):
    # A missing PDF blocks only a change of the PDF path, not other settings.
    c, _, overrides = env
    monkeypatch.setenv("SVTG_PDF_PATH", "data/missing.pdf")
    config.reset_settings_cache()
    r = c.put("/api/settings", json={"temperature": 0.5})
    assert r.status_code == 200 and r.json()["overridden"] == ["temperature"]
    assert overrides.exists()


def test_settings_override_roundtrip(env):
    c, _, overrides = env
    r = c.put("/api/settings", json={"max_steps": 4, "llm_provider": "gemini", "price_input_per_mtok": "", "demo_delay_ms": 100})
    assert r.status_code == 200
    body = r.json()
    assert body["values"]["max_steps"] == 4 and "max_steps" in body["overridden"]
    assert body["key_present"] is True and body["mode"] == "live"
    assert config.get_settings().max_steps == 4
    assert KEY not in overrides.read_text(encoding="utf-8")
    r = c.delete("/api/settings")
    assert r.json()["values"]["max_steps"] == 6 and not overrides.exists()


def test_test_connection_demo(env, monkeypatch):
    c, _, _ = env
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    config.reset_settings_cache()
    body = c.post("/api/settings/test").json()
    assert body["ok"] is True and body["provider"] == "demo" and "Demo mode" in body["message"]


def test_test_connection_reports_failure(env, monkeypatch):
    c, _, _ = env
    from app.llm.base import LLMError
    from app.llm.gemini import GeminiProvider

    def boom(self, request):
        raise LLMError("Gemini call failed (ClientError): 400 API key not valid")

    monkeypatch.setattr(GeminiProvider, "complete", boom)
    c.put("/api/settings", json={"llm_provider": "gemini"})
    body = c.post("/api/settings/test").json()
    assert body["ok"] is False and "API key not valid" in body["message"]
    assert KEY not in str(body)


def test_usage_totals(env):
    c, store, _ = env
    two_runs(store)
    u = c.get("/api/settings/usage").json()
    assert u["total_results"] == 8 and u["total_tokens"] == 1200
    assert u["by_model"][0]["provider"] == "demo"


def test_metrics_meta(env):
    c, _, _ = env
    keys = [m["key"] for m in c.get("/api/meta/metrics").json()]
    assert keys[0] == "dx_top1" and "missed_escalation" in keys


def test_saving_one_setting_does_not_override_prices(env):
    c, _, overrides = env
    body = c.put("/api/settings", json={"gemini_model": "gemini-x"}).json()
    assert body["overridden"] == ["gemini_model"]
    assert "price_input_per_mtok" not in overrides.read_text(encoding="utf-8")
