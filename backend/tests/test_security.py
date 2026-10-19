"""Release hardening: read-only public mode, access code + lockout, sessions, rate limit, daily budget,
per-run case cap, demo exclusion in production, headers, body limits, SVTG passage gating, redaction."""

import json

import pytest
from fastapi.testclient import TestClient

from app import config, security
from app.agent import manager as manager_mod
from app.main import app
from app.storage.db import Store, utc_day

CODE = "correct horse battery staple"


@pytest.fixture
def store(_isolated):
    return _isolated


def env(monkeypatch, **values):
    for k, v in values.items():
        monkeypatch.setenv(k, str(v))
    config.reset_settings_cache()


@pytest.fixture
def prod(monkeypatch, store):
    env(monkeypatch, APP_ENV="production", ADMIN_ACCESS_CODE=CODE, SESSION_SECRET="s" * 40)
    return TestClient(app, base_url="https://testserver")


def unlock(c: TestClient, code: str = CODE):
    return c.post("/api/auth/unlock", json={"code": code})


def add_run(store: Store, provider: str, tokens: int = 0, cases=("BOV-WD-007",), page: int = 36) -> str:
    rid = store.create_run(provider=provider, model=provider + "-model", prompt_version="v2", conditions=["C0"],
                           case_ids=list(cases), interview=False, temperature=0.0)
    for cid in cases:
        store.add_result(rid, {"case_id": cid, "condition": "C0", "interview": False, "status": "ok",
                               "answer": {"citations": [{"source": "SVTG", "page": page}]}, "trace": [],
                               "tokens_in": tokens, "tokens_out": 0})
    store.finish_run(rid)
    return rid


# ---------- public read-only mode ----------

READ_ONLY_OK = ["/api/cases", "/api/drugs", "/api/runs", "/api/results/latest", "/api/meta/metrics", "/api/health",
                "/api/cases/export", "/api/drugs/export", "/api/budget", "/api/auth/status"]
BLOCKED = [
    ("POST", "/api/runs", {"case_ids": ["BOV-WD-007"]}),
    ("POST", "/api/runs/x/cancel", None),
    ("POST", "/api/cases", {}),
    ("PUT", "/api/cases/BOV-WD-007", {}),
    ("DELETE", "/api/cases/BOV-WD-007", None),
    ("POST", "/api/cases/import", []),
    ("POST", "/api/drugs", {}),
    ("DELETE", "/api/drugs?key=cat|paracetamol", None),
    ("GET", "/api/settings", None),
    ("PUT", "/api/settings", {"temperature": 0}),
    ("POST", "/api/settings/test", None),
    ("GET", "/api/review/queue", None),
    ("PUT", "/api/review", {"result_id": 1, "reviewer": "a", "rating": "acceptable"}),
    ("GET", "/api/search?q=milk", None),
]


def test_public_can_read(prod):
    for url in READ_ONLY_OK:
        assert prod.get(url).status_code == 200, url


@pytest.mark.parametrize("method,url,body", BLOCKED)
def test_public_cannot_write_or_run(prod, method, url, body):
    r = prod.request(method, url, json=body)
    assert r.status_code == 401, (url, r.status_code, r.text)
    assert "access code" in r.json()["detail"]


def test_health_reports_mode_and_release_fields(prod):
    h = prod.get("/api/health").json()
    assert h["mode"] == "public" and h["access_required"] is True and h["environment"] == "production"
    assert h["version"] == "1.1.0" and h["database"]["ok"] is True
    assert h["benchmark"]["version"] == "1.0.0" and len(h["benchmark"]["hash"]) == 64 and h["benchmark"]["frozen"]
    raw = prod.get("/api/health").text
    assert "sqlite:" not in raw and "postgresql" not in raw.replace('"engine":"postgresql"', "")  # never the URL
    unlock(prod)
    assert prod.get("/api/health").json()["mode"] == "admin"


# ---------- access code, cookie, lockout ----------

def test_unlock_sets_signed_httponly_cookie(prod):
    r = unlock(prod)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "secure" in cookie
    assert CODE.lower() not in cookie
    assert prod.get("/api/settings").status_code == 200
    assert prod.get("/api/auth/status").json()["admin"] is True
    prod.post("/api/auth/lock")
    assert prod.get("/api/settings").status_code == 401


def test_tampered_or_forged_cookie_is_rejected(prod):
    unlock(prod)
    token = prod.cookies.get(security.COOKIE)
    body, sig = token.rsplit(".", 1)
    prod.cookies.clear()
    prod.cookies.set(security.COOKIE, body + "." + sig[:-2] + ("AA" if not sig.endswith("AA") else "BB"))
    assert prod.get("/api/settings").status_code == 401
    prod.cookies.set(security.COOKIE, "eyJyIjoiYWRtaW4iLCJleHAiOjk5OTk5OTk5OTl9.x")
    assert prod.get("/api/settings").status_code == 401


def test_session_expires():
    s = config.Settings(_env_file=None, admin_access_code=CODE, session_hours=1)
    token = security.make_session(s, now=1000.0)
    assert security.read_session(token, s, now=1000.0 + 3599)
    assert not security.read_session(token, s, now=1000.0 + 3601)
    # changing the code ends every session
    assert not security.read_session(token, config.Settings(_env_file=None, admin_access_code="other"), now=1001.0)


def test_lockout_after_repeated_wrong_codes(prod):
    for left in (4, 3, 2, 1):
        r = unlock(prod, "wrong")
        assert r.status_code == 401 and r.json()["attempts_left"] == left
    r = unlock(prod, "wrong")
    assert r.status_code == 429 and "Too many wrong codes" in r.json()["detail"]
    assert int(r.headers["retry-after"]) > 0
    # even the right code is refused while locked out
    assert unlock(prod).status_code == 429
    assert prod.get("/api/auth/status").json()["locked_for_s"] > 0


def test_production_without_code_is_permanently_read_only(monkeypatch, store):
    env(monkeypatch, APP_ENV="production")
    c = TestClient(app)
    assert c.get("/api/auth/status").json()["unlock_available"] is False
    assert unlock(c, "anything").status_code == 403
    assert c.post("/api/runs", json={"case_ids": ["BOV-WD-007"]}).status_code == 401


# ---------- rate limit, budget, case cap ----------

def test_rate_limit_per_ip(monkeypatch, store):
    env(monkeypatch, RATE_LIMIT_PER_MINUTE=10)
    c = TestClient(app)
    codes = [c.get("/api/cases").status_code for _ in range(12)]
    assert codes[:10] == [200] * 10 and codes[10:] == [429, 429]
    r = c.get("/api/drugs")
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "Too many requests" in r.json()["detail"]
    assert c.get("/api/health").status_code == 200  # health checks are exempt


def test_daily_budget_blocks_new_runs(monkeypatch, store):
    env(monkeypatch, MAX_DAILY_TOKENS=1000)
    add_run(store, "gemini", tokens=1200)
    c = TestClient(app)
    b = c.get("/api/budget").json()
    assert b == {"cap": 1000, "used": 1200, "remaining": 0, "exhausted": True, "max_cases_per_run": 30}
    r = c.post("/api/runs", json={"case_ids": ["BOV-WD-007"], "force": True})
    assert r.status_code == 429 and "Daily token budget reached" in r.json()["detail"]


def test_budget_counts_only_live_uncached_tokens_from_today(store):
    add_run(store, "demo", tokens=5000)
    add_run(store, "gemini", tokens=300)
    rid = store.create_run(provider="gemini", model="m", prompt_version="v2", conditions=["C0"], case_ids=["BOV-001"],
                           interview=False)
    store.add_result(rid, {"case_id": "BOV-001", "condition": "C0", "interview": False, "status": "ok",
                           "answer": None, "trace": [], "tokens_in": 999, "tokens_out": 0, "cached": True})
    assert store.tokens_on(utc_day()) == 300
    assert store.tokens_on("2999-01-01") == 0


def test_imported_snapshot_does_not_count_against_today(store):
    from app.snapshot import load_snapshot

    load_snapshot(store, config.Settings(_env_file=None).snapshot_file)
    assert store.tokens_on(utc_day()) == 0


def test_budget_stops_a_running_run(monkeypatch, store):
    """A run that crosses the cap stops after the step that crossed it, with status budget_exhausted."""
    from app.agent import manager as mm

    real = mm.run_one

    def spend(**kw):
        r = real(**kw)
        r["tokens_in"], r["cached"] = 600, False
        return r

    from app.llm.demo import DemoProvider

    class LiveLike(DemoProvider):  # demo answers, but counted like a live model
        name = "gemini"

    s = config.Settings(_env_file=None, max_daily_tokens=1000)
    live = LiveLike()
    monkeypatch.setattr(mm, "run_one", spend)
    monkeypatch.setattr(mm.manager, "_provider", lambda settings: live)
    run = mm.manager.start(s, ["BOV-WD-007"], None, False, True)
    events: list[tuple[str, dict]] = []
    emit = lambda t, d: events.append((t, d))  # noqa: E731
    first = mm.manager.run_step(s, mm.manager.prepare_step(s, run["run_id"], "BOV-WD-007", "C0"), emit)
    assert first["stop"] is None
    second = mm.manager.run_step(s, mm.manager.prepare_step(s, run["run_id"], "BOV-WD-007", "C1"), emit)
    assert second["stop"] == "budget" and second["n_done"] == 2
    assert store.get_run(run["run_id"])["status"] == "budget_exhausted"
    assert any(t == "run_error" and "budget" in d["error"] for t, d in events)
    with pytest.raises(mm.StepError) as e:
        mm.manager.prepare_step(s, run["run_id"], "BOV-WD-007", "C2")
    assert e.value.status in (409, 429)


def test_max_cases_per_run(monkeypatch, store):
    env(monkeypatch, MAX_CASES_PER_RUN=2)
    c = TestClient(app)
    r = c.post("/api/runs", json={"case_ids": ["BOV-WD-007", "CAN-013", "FEL-SAFE-004"]})
    assert r.status_code == 400 and "limit is 2" in r.json()["detail"]


# ---------- demo data never in production ----------

def test_production_refuses_demo_runs(prod):
    unlock(prod)
    r = prod.post("/api/runs", json={"case_ids": ["BOV-WD-007"]})
    assert r.status_code == 400 and "No live model" in r.json()["detail"]


def test_production_hides_demo_results(prod, store):
    demo = add_run(store, "demo")
    live = add_run(store, "gemini")
    assert [r["id"] for r in prod.get("/api/runs").json()] == [live]
    assert prod.get(f"/api/runs/{demo}").status_code == 404
    assert prod.get("/api/scorecard", params={"run_id": demo}).status_code == 404
    assert prod.get("/api/scorecard/export.csv", params={"run_id": demo}).status_code == 404
    latest = prod.get("/api/results/latest").json()
    assert {v["run_id"] for by_c in latest.values() for v in by_c.values()} == {live}
    assert store.delete_demo_runs() == 1 and Store(store.url, hide_demo=False).count_runs() == 1


# ---------- headers, CORS, body limits ----------

def test_security_headers(prod):
    r = prod.get("/api/health")
    h = r.headers
    assert "frame-ancestors 'none'" in h["content-security-policy"] and "default-src 'self'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["x-frame-options"] == "DENY"
    assert h["strict-transport-security"].startswith("max-age=")


def test_cross_origin_writes_refused_and_cors_limited(monkeypatch, store):
    env(monkeypatch, ALLOWED_ORIGINS="https://vab.example.org")
    c = TestClient(app)
    assert c.post("/api/auth/lock", headers={"Origin": "https://evil.example"}).status_code == 403
    assert c.post("/api/auth/lock", headers={"Origin": "http://testserver"}).status_code == 200
    # CORS middleware is configured at import from the environment; check the guard's allow-list instead.
    s = config.get_settings()
    assert s.origins == ["https://vab.example.org"]


def test_body_size_limit(monkeypatch, store):
    env(monkeypatch, MAX_BODY_BYTES=10_000)
    c = TestClient(app)
    big = json.dumps([{"x": "a" * 20_000}])
    r = c.post("/api/cases/import", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_text_fields_are_size_limited(monkeypatch, tmp_path):
    from app.data import editor, loaders

    case = json.loads(loaders.CASES_PATH.read_text(encoding="utf-8"))[0]
    case["history"] = "x" * 5000
    with pytest.raises(editor.EditError) as e:
        editor.validate_case(case)
    assert any(err["loc"] == ["history"] for err in e.value.errors)
    with pytest.raises(editor.EditError, match="limit is 1000"):
        editor.import_cases([case] * 1001, "merge")


def test_validation_errors_do_not_echo_input(prod):
    unlock(prod)
    r = prod.put("/api/review", json={"result_id": "x" * 50, "reviewer": "a", "rating": "nope"})
    assert r.status_code == 422 and "x" * 50 not in r.text


def test_unhandled_errors_hide_the_stack(monkeypatch, store):
    from app.api import data as data_api

    def boom():
        raise RuntimeError("secret internals AIzaSyA" + "b" * 33)

    monkeypatch.setattr(data_api, "_cases", boom)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/cases")
    assert r.status_code == 500
    assert r.json()["detail"].startswith("Internal server error (reference ")
    assert "Traceback" not in r.text and "secret internals" not in r.text


# ---------- SVTG passages ----------

def test_public_gets_only_cited_svtg_pages(prod, store):
    store.replace_chunks([{"chunk_id": f"p{p}-c1", "page": p, "printed_page": p - 18, "section": "s",
                           "text": f"Passage on page {p}."} for p in (36, 250)], {"pages": 406})
    add_run(store, "gemini")  # cites page 36
    r = prod.get("/api/svtg/pages/36")
    assert r.status_code == 200 and r.json()["source"]["url"].startswith("https://dahd.gov.in/")
    assert prod.get("/api/svtg/pages/250").status_code == 404
    unlock(prod)
    assert prod.get("/api/svtg/pages/250").status_code == 200


def test_pdf_is_never_served(prod):
    for url in ("/StandardVeterinaryTreatment.pdf", "/data/StandardVeterinaryTreatment.pdf", "/../data/StandardVeterinaryTreatment.pdf",
                "/api/svtg/pdf", "/assets/../../data/StandardVeterinaryTreatment.pdf"):
        r = prod.get(url)
        assert r.headers.get("content-type", "").split(";")[0] != "application/pdf", url
        assert not r.content.startswith(b"%PDF"), url


# ---------- redaction ----------

def test_redact_removes_keys_and_configured_secrets():
    s = config.Settings(_env_file=None, gemini_api_key="my-very-secret-value-123", admin_access_code="opensesame")
    text = "key=AIzaSyD" + "x" * 32 + " token sk-" + "y" * 30 + " my-very-secret-value-123 opensesame Bearer abcdefghijklmnopqrstu"
    out = security.redact(text, s)
    assert "AIza" not in out and "sk-yyyy" not in out and "my-very-secret" not in out and "opensesame" not in out
    assert "abcdefghijklmnop" not in out


def test_log_filter_redacts(caplog):
    import logging

    security.install_log_redaction()
    log = logging.getLogger("vetagentbench")
    with caplog.at_level(logging.INFO, logger="vetagentbench"):
        log.info("calling with %s", "AIzaSy" + "Q" * 33)
    assert "AIza" not in caplog.text and "[redacted]" in caplog.text


def test_run_records_release_metadata(store):
    s = config.Settings(_env_file=None)
    summary = manager_mod.manager.start(s, ["BOV-WD-007"], ["C0"], False, True)
    run = store.get_run(summary["run_id"])
    assert run["temperature"] == 0.0 and run["prompt_version"] and run["model"] and run["created_at"]
    assert run["benchmark_version"] == "1.0.0" and len(run["benchmark_hash"]) == 64


def test_frozen_snapshot_reproduces():
    from app.snapshot import read_snapshot, verify_snapshot

    path = config.Settings(_env_file=None).snapshot_file
    assert verify_snapshot(path) == []
    data = read_snapshot(path)
    assert data["run"]["provider"] != "demo" and data["run"]["n_total"] == len(data["results"]) == 145
    assert all(r["status"] == "ok" for r in data["results"])


def test_snapshot_loads_once(store):
    from app.snapshot import load_snapshot

    path = config.Settings(_env_file=None).snapshot_file
    rid = load_snapshot(store, path)
    assert rid and load_snapshot(store, path) is None
    assert len(store.results(rid)) == 145 and store.get_run(rid)["benchmark_version"] == "1.0.0"
