"""Runs API in demo mode: start, SSE stream, cancel, conflict, history, latest, passages."""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agent import manager as manager_mod
from app.config import Settings, get_settings
from app.main import app
from app.storage.db import Store

PDF_PRESENT = Settings(_env_file=None).pdf_path.is_file()


@pytest.fixture
def client(tmp_path: Path):
    m = manager_mod.manager
    old = (m._store, m._runs, m._active)
    m._store, m._runs, m._active = Store(tmp_path / "runs.db"), {}, None
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # demo, no key
    yield TestClient(app)
    app.dependency_overrides.clear()
    m._store, m._runs, m._active = old


def read_sse(client: TestClient, run_id: str) -> list[tuple[str, dict]]:
    events = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        etype = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                etype = line[7:]
            elif line.startswith("data: "):
                events.append((etype, json.loads(line[6:])))
    return events


def wait_done(client: TestClient, run_id: str, timeout: float = 30) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if client.get("/api/runs/active").json() is None:
            return
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_run_streams_steps_and_results(client):
    res = client.post("/api/runs", json={"case_ids": ["BOV-WD-007"], "force": True})
    assert res.status_code == 202
    run_id = res.json()["run_id"]
    assert res.json()["n_total"] == 5

    events = read_sse(client, run_id)
    types = [t for t, _ in events]
    assert types[0] == "run_started" and types[-1] == "run_done"
    assert types.count("result_started") == 5 and types.count("result_done") == 5
    assert types.count("step") > 10

    # steps arrive before their result, per condition
    c2 = [(t, d) for t, d in events if d.get("condition") == "C2"]
    assert c2[0][0] == "result_started" and c2[-1][0] == "result_done"
    assert {d["step"]["kind"] for t, d in c2 if t == "step"} >= {"llm", "tool"}

    done = [d for t, d in events if t == "result_done"]
    assert all(d["result"]["status"] == "ok" for d in done)
    assert all("verdict" in d["result"] and "trace" in d["result"] for d in done)
    assert events[-1][1]["status"] == "done"


def test_replay_after_finish_and_history(client):
    run_id = client.post("/api/runs", json={"case_ids": ["CAP-005"], "conditions": ["C0", "C1"]}).json()["run_id"]
    wait_done(client, run_id)
    replay = read_sse(client, run_id)  # late client gets the full log
    assert [t for t, _ in replay].count("result_done") == 2

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "done" and len(run["results"]) == 2
    assert client.get("/api/runs").json()[0]["id"] == run_id

    rid = run["results"][1]["id"]
    full = client.get(f"/api/results/{rid}").json()
    assert full["condition"] == "C1" and full["trace"][0]["name"] == "search_guidelines"
    assert full["provider"] == "demo"


def test_latest_results(client):
    run_id = client.post("/api/runs", json={"case_ids": ["BOV-009"], "conditions": ["C2", "C4"], "force": True}).json()["run_id"]
    wait_done(client, run_id)
    latest = client.get("/api/results/latest").json()
    assert set(latest["BOV-009"]) == {"C2", "C4"}
    c4 = latest["BOV-009"]["C4"]
    assert c4["answer"]["drug_status"] == "banned_in_india"
    assert c4["verdict"]["false_safe"] is False
    assert "trace" not in c4
    assert client.get("/api/results/latest", params={"interview": True}).json() == {}


def test_interview_run(client):
    run_id = client.post("/api/runs", json={"case_ids": ["CAN-013"], "interview": True}).json()["run_id"]
    events = read_sse(client, run_id)
    done = [d for t, d in events if t == "result_done"]
    assert [d["condition"] for d in done] == ["C0", "C3"]
    assert any(d["step"]["kind"] == "owner" for t, d in events if t == "step")
    assert set(client.get("/api/results/latest", params={"interview": True}).json()["CAN-013"]) == {"C0", "C3"}


def test_cancel(client, monkeypatch):
    # slow the demo provider down so cancel lands mid-run
    from app.llm.demo import DemoProvider

    original = DemoProvider.complete

    def slow(self, request):
        time.sleep(0.05)
        return original(self, request)

    monkeypatch.setattr(DemoProvider, "complete", slow)
    ids = ["BOV-001", "BOV-002", "BOV-003", "BOV-004"]
    run_id = client.post("/api/runs", json={"case_ids": ids, "force": True}).json()["run_id"]
    time.sleep(0.3)
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 200
    events = read_sse(client, run_id)
    assert events[-1][0] == "run_done" and events[-1][1]["status"] == "cancelled"
    assert [t for t, _ in events].count("result_done") < 20
    assert client.post(f"/api/runs/{run_id}/cancel").status_code == 404


def test_conflict_and_validation(client, monkeypatch):
    from app.llm.demo import DemoProvider

    original = DemoProvider.complete
    monkeypatch.setattr(DemoProvider, "complete", lambda self, r: (time.sleep(0.05), original(self, r))[1])
    run_id = client.post("/api/runs", json={"case_ids": ["BOV-001", "BOV-002"], "force": True}).json()["run_id"]
    second = client.post("/api/runs", json={"case_ids": ["BOV-003"]})
    assert second.status_code == 409 and run_id in second.json()["detail"]
    client.post(f"/api/runs/{run_id}/cancel")
    wait_done(client, run_id)

    assert client.post("/api/runs", json={"case_ids": ["NOPE-001"]}).status_code == 400
    bad = client.post("/api/runs", json={"case_ids": ["CAN-013"], "interview": True, "conditions": ["C2"]})
    assert bad.status_code == 400 and "not available" in bad.json()["detail"]
    assert client.post("/api/runs", json={"case_ids": []}).status_code == 422


def test_unknown_run_stream_404(client):
    assert client.get("/api/runs/nope/events").status_code == 404
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/results/999999").status_code == 404


@pytest.mark.skipif(not PDF_PRESENT, reason="SVTG PDF not present")
def test_svtg_page(client):
    body = client.get("/api/svtg/pages/175").json()
    assert body["printed_page"] == 157
    assert any("Buparvaquone" in c["text"] for c in body["chunks"])
    assert client.get("/api/svtg/pages/2").status_code == 404


def test_run_stops_on_daily_quota(client, monkeypatch):
    from app.llm.base import QuotaExhausted
    from app.llm.demo import DemoProvider

    calls = {"n": 0}

    def exhausted(self, request):
        calls["n"] += 1
        raise QuotaExhausted("Gemini daily quota exhausted (GenerateRequestsPerDayPerProjectPerModel-FreeTier).")

    monkeypatch.setattr(DemoProvider, "complete", exhausted)
    run_id = client.post("/api/runs", json={"case_ids": ["BOV-001", "BOV-002", "BOV-003"], "force": True}).json()["run_id"]
    events = read_sse(client, run_id)
    done = [d for t, d in events if t == "result_done"]
    assert len(done) == 1 and calls["n"] == 1  # stopped after the first failure, not 15
    assert any(t == "run_error" and "daily quota" in d["error"] for t, d in events)
    assert events[-1][1]["status"] == "quota_exhausted"
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "quota_exhausted"
