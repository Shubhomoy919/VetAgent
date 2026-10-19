"""Runs API in demo mode, one request per step: create, step (SSE or JSON), finish, cancel, resume, timeout,
conflict, history, latest results, passages."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)  # demo, no key
    yield TestClient(app)
    app.dependency_overrides.clear()


def step_sse(client: TestClient, run_id: str, case_id: str, condition: str) -> list[tuple[str, dict]]:
    events = []
    with client.stream("POST", f"/api/runs/{run_id}/step", json={"case_id": case_id, "condition": condition},
                       headers={"Accept": "text/event-stream"}) as r:
        assert r.status_code == 200, r.read()
        assert r.headers["content-type"].startswith("text/event-stream")
        etype = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                etype = line[7:]
            elif line.startswith("data: "):
                events.append((etype, json.loads(line[6:])))
    return events


def run_all(client: TestClient, body: dict) -> tuple[dict, list[tuple[str, dict]]]:
    """What the browser does: create the run, then one step per case and condition, then finish."""
    res = client.post("/api/runs", json=body)
    assert res.status_code == 202, res.text
    run = res.json()
    events: list[tuple[str, dict]] = []
    for cid in run["case_ids"]:
        for cond in run["conditions"]:
            evs = step_sse(client, run["run_id"], cid, cond)
            events += evs
            if any(t == "result_done" and d["stop"] for t, d in evs):
                return client.post(f"/api/runs/{run['run_id']}/finish").json(), events
    return client.post(f"/api/runs/{run['run_id']}/finish").json(), events


def test_run_one_step_per_request_streams_steps_and_results(client):
    final, events = run_all(client, {"case_ids": ["BOV-WD-007"], "force": True})
    types = [t for t, _ in events]
    assert types.count("result_started") == 5 and types.count("result_done") == 5
    assert types.count("step") > 10
    c2 = [(t, d) for t, d in events if d.get("condition") == "C2"]
    assert c2[0][0] == "result_started" and c2[-1][0] == "result_done"
    assert {d["step"]["kind"] for t, d in c2 if t == "step"} >= {"llm", "tool"}
    done = [d for t, d in events if t == "result_done"]
    assert all(d["result"]["status"] == "ok" and "verdict" in d["result"] and "trace" in d["result"] for d in done)
    assert [d["n_done"] for d in done] == [1, 2, 3, 4, 5]
    assert final["status"] == "done" and final["n_done"] == 5
    assert len(final["done"]) == 5


def test_step_as_json_when_streaming_is_not_requested(client):
    run = client.post("/api/runs", json={"case_ids": ["CAP-005"], "conditions": ["C1"]}).json()
    body = client.post(f"/api/runs/{run['run_id']}/step", json={"case_id": "CAP-005", "condition": "C1"}).json()
    assert body["result"]["status"] == "ok" and body["result"]["trace"][0]["name"] == "search_guidelines"
    assert body["n_done"] == 1 and body["stop"] is None
    assert [e["type"] for e in body["events"]][0] == "result_started"
    assert body["events"][-1]["type"] == "result_done"
    # the last step of a run closes it
    assert client.get(f"/api/runs/{run['run_id']}").json()["status"] == "done"


def test_history_and_result_detail(client):
    final, _ = run_all(client, {"case_ids": ["CAP-005"], "conditions": ["C0", "C1"]})
    run = client.get(f"/api/runs/{final['run_id']}").json()
    assert run["status"] == "done" and len(run["results"]) == 2
    assert client.get("/api/runs").json()[0]["id"] == final["run_id"]
    rid = run["results"][1]["id"]
    full = client.get(f"/api/results/{rid}").json()
    assert full["condition"] == "C1" and full["trace"][0]["name"] == "search_guidelines"
    assert full["provider"] == "demo"


def test_step_checks(client):
    run = client.post("/api/runs", json={"case_ids": ["BOV-009"], "conditions": ["C0"]}).json()
    rid = run["run_id"]
    assert client.post(f"/api/runs/{rid}/step", json={"case_id": "BOV-001", "condition": "C0"}).status_code == 400
    assert client.post(f"/api/runs/{rid}/step", json={"case_id": "BOV-009", "condition": "C2"}).status_code == 400
    assert client.post("/api/runs/nope/step", json={"case_id": "BOV-009", "condition": "C0"}).status_code == 404
    assert client.post(f"/api/runs/{rid}/step", json={"case_id": "BOV-009", "condition": "C0"}).status_code == 200
    # each step runs once per run; the run is closed after its last step
    again = client.post(f"/api/runs/{rid}/step", json={"case_id": "BOV-009", "condition": "C0"})
    assert again.status_code == 409


def test_resume_after_reload(client):
    run = client.post("/api/runs", json={"case_ids": ["BOV-009"], "conditions": ["C0", "C1"]}).json()
    step_sse(client, run["run_id"], "BOV-009", "C0")
    active = client.get("/api/runs/active").json()
    assert active["run_id"] == run["run_id"] and active["status"] == "running"
    assert active["done"] == [{"case_id": "BOV-009", "condition": "C0"}]
    step_sse(client, run["run_id"], "BOV-009", "C1")
    assert client.get("/api/runs/active").json() is None


def test_latest_results(client):
    run_all(client, {"case_ids": ["BOV-009"], "conditions": ["C2", "C4"], "force": True})
    latest = client.get("/api/results/latest").json()
    assert set(latest["BOV-009"]) == {"C2", "C4"}
    c4 = latest["BOV-009"]["C4"]
    assert c4["answer"]["drug_status"] == "banned_in_india"
    assert c4["verdict"]["false_safe"] is False
    assert "trace" not in c4
    assert client.get("/api/results/latest", params={"interview": True}).json() == {}


def test_case_results_lists_history_newest_first(client):
    for _ in range(2):
        run_all(client, {"case_ids": ["BOV-009"], "conditions": ["C0"], "force": True})
    rows = client.get("/api/results", params={"case_id": "BOV-009"}).json()
    assert len([r for r in rows if r["condition"] == "C0"]) >= 2
    assert [r["id"] for r in rows] == sorted((r["id"] for r in rows), reverse=True)
    assert all(r["case_id"] == "BOV-009" and "verdict" in r and "trace" not in r and r["run_id"] for r in rows)
    assert client.get("/api/results", params={"case_id": "NOPE-1"}).status_code == 404


def test_cache_hit_on_second_run(client):
    run_all(client, {"case_ids": ["BOV-001"], "conditions": ["C1"]})
    _, events = run_all(client, {"case_ids": ["BOV-001"], "conditions": ["C1"]})
    done = [d for t, d in events if t == "result_done"][0]
    assert done["result"]["cached"] is True
    assert any(t == "step" and d["step"]["name"] == "cache_hit" for t, d in events)


def test_interview_run(client):
    _, events = run_all(client, {"case_ids": ["CAN-013"], "interview": True})
    done = [d for t, d in events if t == "result_done"]
    assert [d["condition"] for d in done] == ["C0", "C3"]
    assert any(d["step"]["kind"] == "owner" for t, d in events if t == "step")
    assert set(client.get("/api/results/latest", params={"interview": True}).json()["CAN-013"]) == {"C0", "C3"}


def test_cancel(client):
    run = client.post("/api/runs", json={"case_ids": ["BOV-001", "BOV-002"], "force": True}).json()
    step_sse(client, run["run_id"], "BOV-001", "C0")
    assert client.post(f"/api/runs/{run['run_id']}/cancel").status_code == 200
    detail = client.get(f"/api/runs/{run['run_id']}").json()
    assert detail["status"] == "cancelled" and len(detail["results"]) == 1
    assert client.post(f"/api/runs/{run['run_id']}/cancel").status_code == 404
    late = client.post(f"/api/runs/{run['run_id']}/step", json={"case_id": "BOV-001", "condition": "C1"})
    assert late.status_code == 409 and "cancelled" in late.json()["detail"]
    # finish with cancelled=true does the same and is idempotent
    assert client.post(f"/api/runs/{run['run_id']}/finish", json={"cancelled": True}).json()["status"] == "cancelled"


def test_conflict_and_validation(client):
    run = client.post("/api/runs", json={"case_ids": ["BOV-001"], "force": True}).json()
    second = client.post("/api/runs", json={"case_ids": ["BOV-003"]})
    assert second.status_code == 409 and run["run_id"] in second.json()["detail"]
    client.post(f"/api/runs/{run['run_id']}/cancel")
    assert client.post("/api/runs", json={"case_ids": ["BOV-003"], "conditions": ["C0"]}).status_code == 202
    client.post(f"/api/runs/{client.get('/api/runs/active').json()['run_id']}/cancel")

    assert client.post("/api/runs", json={"case_ids": ["NOPE-001"]}).status_code == 400
    bad = client.post("/api/runs", json={"case_ids": ["CAN-013"], "interview": True, "conditions": ["C2"]})
    assert bad.status_code == 400 and "not available" in bad.json()["detail"]
    assert client.post("/api/runs", json={"case_ids": []}).status_code == 422


def test_abandoned_run_is_interrupted_and_does_not_block(client, _isolated):
    from sqlalchemy import update

    from app.storage import schema as t

    run = client.post("/api/runs", json={"case_ids": ["BOV-001"], "conditions": ["C0"]}).json()
    with _isolated._tx() as c:  # no progress for an hour: the browser was closed
        c.execute(update(t.runs).values(updated_at="2000-01-01T00:00:00+00:00"))
    assert client.get("/api/runs/active").json() is None
    assert client.get(f"/api/runs/{run['run_id']}").json()["status"] == "interrupted"
    assert client.post("/api/runs", json={"case_ids": ["BOV-002"], "conditions": ["C0"]}).status_code == 202


def test_step_timeout_is_stored_and_can_be_retried(client, monkeypatch):
    from app.llm.demo import DemoProvider

    original = DemoProvider.complete
    monkeypatch.setattr(DemoProvider, "complete", lambda self, r: (time.sleep(1.5), original(self, r))[1])
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, step_deadline_s=1)
    run = client.post("/api/runs", json={"case_ids": ["BOV-001"], "conditions": ["C3"]}).json()
    events = step_sse(client, run["run_id"], "BOV-001", "C3")
    done = [d for t, d in events if t == "result_done"][0]
    assert done["result"]["status"] == "timeout"
    assert "Timed out" in done["result"]["error"] and "Retry" in done["result"]["error"]
    final = client.get(f"/api/runs/{run['run_id']}").json()
    assert final["status"] == "done_with_errors" and final["results"][0]["status"] == "timeout"
    # Retry = a new run for that case and condition; with the normal speed and limit it completes.
    monkeypatch.setattr(DemoProvider, "complete", original)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    _, events = run_all(client, {"case_ids": ["BOV-001"], "conditions": ["C3"]})
    assert [d for t, d in events if t == "result_done"][0]["result"]["status"] == "ok"


def test_unknown_run_404(client):
    assert client.get("/api/runs/nope").status_code == 404
    assert client.post("/api/runs/nope/finish").status_code == 404
    assert client.get("/api/results/999999").status_code == 404


def test_svtg_page(client, svtg):
    body = client.get("/api/svtg/pages/175").json()
    assert body["printed_page"] == 157
    assert any("Buparvaquone" in c["text"] for c in body["chunks"])
    assert client.get("/api/svtg/pages/2").status_code == 404


def test_svtg_page_from_test_passages(client, fake_svtg):
    body = client.get("/api/svtg/pages/110").json()
    assert body["chunks"][0]["section"] == "3.1 Rabies"
    assert "dahd.gov.in" in body["source"]["url"]


def test_run_stops_on_daily_quota(client, monkeypatch):
    from app.llm.base import QuotaExhausted
    from app.llm.demo import DemoProvider

    calls = {"n": 0}

    def exhausted(self, request):
        calls["n"] += 1
        raise QuotaExhausted("Gemini daily quota exhausted (GenerateRequestsPerDayPerProjectPerModel-FreeTier).")

    monkeypatch.setattr(DemoProvider, "complete", exhausted)
    final, events = run_all(client, {"case_ids": ["BOV-001", "BOV-002", "BOV-003"], "force": True})
    done = [d for t, d in events if t == "result_done"]
    assert len(done) == 1 and calls["n"] == 1 and done[0]["stop"] == "quota"  # stopped after the first failure
    assert any(t == "run_error" and "daily quota" in d["error"] for t, d in events)
    assert final["status"] == "quota_exhausted"
    late = client.post(f"/api/runs/{final['run_id']}/step", json={"case_id": "BOV-001", "condition": "C1"})
    assert late.status_code == 409
