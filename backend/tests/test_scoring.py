import csv
import io
import math

import pytest
from fastapi.testclient import TestClient

from app.data.loaders import read_cases_file
from app.main import app
from app.scoring.metrics import CSV_HEADER, build_scorecard, scorecard_csv_rows
from app.scoring.stats import mcnemar_exact, wilson

# ---------- Wilson ----------


@pytest.mark.parametrize(
    "k,n,lo,hi",
    [
        (0, 10, 0.0, 0.2775),
        (5, 10, 0.2366, 0.7634),
        (10, 10, 0.7225, 1.0),
        (1, 29, 0.0061, 0.1720),
        (29, 29, 0.8830, 1.0),
    ],
)
def test_wilson_known_values(k, n, lo, hi):
    got = wilson(k, n)
    assert got is not None
    assert got[0] == pytest.approx(lo, abs=5e-4)
    assert got[1] == pytest.approx(hi, abs=5e-4)


def test_wilson_empty_and_invalid():
    assert wilson(0, 0) is None
    with pytest.raises(ValueError):
        wilson(5, 3)


def test_wilson_contains_point_estimate():
    for n in (1, 7, 29):
        for k in range(n + 1):
            lo, hi = wilson(k, n)  # type: ignore[misc]
            assert lo <= k / n <= hi


# ---------- McNemar ----------


@pytest.mark.parametrize(
    "b,c,p",
    [
        (5, 0, 0.0625),  # 2 * (1/2)^5
        (0, 5, 0.0625),
        (3, 3, 1.0),
        (1, 9, 22 / 1024),  # 2 * (C(10,0)+C(10,1)) / 2^10
        (10, 2, 2 * sum(math.comb(12, i) for i in range(3)) / 2**12),
    ],
)
def test_mcnemar_exact(b, c, p):
    assert mcnemar_exact(b, c) == pytest.approx(p)


def test_mcnemar_no_discordant_pairs():
    assert mcnemar_exact(0, 0) is None


# ---------- scorecard aggregation ----------


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in read_cases_file()}


def ans(**kw):
    base = dict(differentials=[], most_likely="x", triage="routine", drug_status="n/a", dose_mg=None,
                withdrawal_days=None, escalate=False, zoonosis_warning=False, see_vet=True, advice="a", citations=[])
    return {**base, **kw}


def res(case_id, cond, answer=None, status="ok", **kw):
    return {"case_id": case_id, "condition": cond, "status": status, "answer": answer, "steps": kw.get("steps", 1),
            "tokens_in": 100, "tokens_out": 50, "latency_ms": 1000, "cost_usd": kw.get("cost", 0.001)}


RUN = {"id": "r1", "provider": "gemini", "model": "m", "n_done": 6, "n_total": 6}


def test_rates_denominators_and_errors(cases):
    results = [
        # C0: BOV-010 correct; BOV-008 says diclofenac safe (false-safe + illegal); BOV-001 error
        res("BOV-010", "C0", ans(most_likely="ketosis", triage="urgent")),
        res("BOV-008", "C0", ans(most_likely="hoof injury", drug_status="safe")),
        res("BOV-001", "C0", None, status="error"),
        # C4: all handled safely
        res("BOV-010", "C4", ans(most_likely="ketosis", triage="urgent")),
        res("BOV-008", "C4", ans(most_likely="hoof injury", drug_status="banned_in_india")),
        res("BOV-001", "C4", ans(most_likely="milk fever", triage="emergency", escalate=True)),
    ]
    sc = build_scorecard(RUN, results, cases)
    assert sc["conditions"] == ["C0", "C4"]
    m = {x["key"]: x["by_condition"] for x in sc["metrics"]}

    assert m["dx_top1"]["C0"]["k"] == 2 and m["dx_top1"]["C0"]["n"] == 2  # error excluded
    assert m["dx_top1"]["C4"]["n"] == 3
    # false-safe applies only to BOV-008 (banned gold drug)
    assert (m["false_safe"]["C0"]["k"], m["false_safe"]["C0"]["n"]) == (1, 1)
    assert (m["false_safe"]["C4"]["k"], m["false_safe"]["C4"]["n"]) == (0, 1)
    assert m["illegal_drug"]["C0"]["k"] == 1
    # withdrawal error not applicable to any of these cases
    assert m["withdrawal_error"]["C0"]["n"] == 0 and m["withdrawal_error"]["C0"]["rate"] is None
    assert sc["usage"]["C0"]["errors"] == 1
    assert any("failed" in w for w in sc["warnings"])


def test_mcnemar_pairs_only_shared_cases(cases):
    results = [
        res("BOV-010", "C0", ans(most_likely="ketosis")),
        res("BOV-002", "C0", ans(most_likely="nope")),
        res("BOV-003", "C0", ans(most_likely="nope")),
        res("BOV-010", "C1", ans(most_likely="nope")),
        res("BOV-002", "C1", ans(most_likely="bloat")),
        res("BOV-003", "C1", ans(most_likely="haemorrhagic septicaemia")),
        res("BOV-004", "C1", ans(most_likely="FMD")),  # no C0 partner
    ]
    sc = build_scorecard(RUN, results, cases)
    t = next(x for x in sc["mcnemar"] if x["metric"] == "dx_top1" and x["a"] == "C0" and x["b"] == "C1")
    assert t["n_pairs"] == 3
    assert (t["only_a"], t["only_b"]) == (1, 2)
    assert t["p"] == pytest.approx(mcnemar_exact(1, 2))


def test_latest_result_per_case_wins(cases):
    results = [
        res("BOV-010", "C0", ans(most_likely="nope")),
        res("BOV-010", "C0", ans(most_likely="ketosis")),  # later row
    ]
    sc = build_scorecard(RUN, results, cases)
    top1 = next(x for x in sc["metrics"] if x["key"] == "dx_top1")["by_condition"]["C0"]
    assert (top1["k"], top1["n"]) == (1, 1)


def test_breakdowns_and_usage(cases):
    results = [
        res("BOV-010", "C2", ans(most_likely="ketosis"), steps=4),
        res("FEL-SAFE-004", "C2", ans(drug_status="safe"), steps=2),
    ]
    sc = build_scorecard(RUN, results, cases)
    species = {r["group"]: r for r in sc["breakdowns"]["species"]}
    assert set(species) == {"BOV", "FEL"}
    assert species["FEL"]["by_condition"]["C2"]["dangerous"]["k"] == 1
    qt = {r["group"] for r in sc["breakdowns"]["question_type"]}
    assert qt == {"diagnosis", "drug_safety"}
    u = sc["usage"]["C2"]
    assert u["avg_steps"] == 3 and u["total_tokens"] == 300 and u["total_cost_usd"] == pytest.approx(0.002)


def test_unknown_cost_propagates(cases):
    sc = build_scorecard(RUN, [res("BOV-010", "C0", ans(), cost=None)], cases)
    assert sc["usage"]["C0"]["total_cost_usd"] is None


def test_demo_warning(cases):
    sc = build_scorecard({**RUN, "provider": "demo"}, [res("BOV-010", "C0", ans())], cases)
    assert any("Demo provider" in w for w in sc["warnings"])


def test_csv_rows(cases):
    sc = build_scorecard(RUN, [res("BOV-010", "C0", ans(most_likely="ketosis")), res("BOV-010", "C1", ans())], cases)
    rows = scorecard_csv_rows(sc)
    assert all(len(r) == len(CSV_HEADER) for r in rows)
    top1 = [r for r in rows if r[3] == "dx_top1"]
    assert [r[6] for r in top1] == ["C0", "C1"]
    assert top1[0][7:10] == [1, 1, 1.0]
    assert any(str(r[3]).startswith("mcnemar:") for r in rows)


# ---------- API ----------


@pytest.fixture
def client(_isolated, cases):
    store = _isolated
    run_id = store.create_run(provider="demo", model="demo", prompt_version="v1", conditions=["C0", "C4"],
                              case_ids=["BOV-010", "BOV-008"], interview=False)
    for r in [
        res("BOV-010", "C0", ans(most_likely="ketosis", triage="urgent")),
        res("BOV-008", "C0", ans(drug_status="safe")),
        res("BOV-010", "C4", ans(most_likely="ketosis", triage="urgent")),
        res("BOV-008", "C4", ans(drug_status="banned_in_india")),
    ]:
        store.add_result(run_id, {**r, "interview": False, "error": None, "trace": [], "rules_fired": [],
                                  "owner_questions": [], "cached": False, "cache_key": "k"})
    store.finish_run(run_id)
    yield TestClient(app), run_id


def test_scorecard_api_default_run(client):
    c, run_id = client
    body = c.get("/api/scorecard").json()
    assert body["run"]["id"] == run_id
    assert body["conditions"] == ["C0", "C4"]
    fs = next(x for x in body["metrics"] if x["key"] == "false_safe")["by_condition"]
    assert fs["C0"]["rate"] == 1.0 and fs["C4"]["rate"] == 0.0


def test_scorecard_csv_and_json_export(client):
    c, run_id = client
    r = c.get("/api/scorecard/export.csv", params={"run_id": run_id})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert f"scorecard-{run_id}.csv" in r.headers["content-disposition"]
    lines = r.text.splitlines()
    assert lines[0].startswith("# disclaimer: Research prototype") and any(ln.startswith("# benchmark_hash: ") for ln in lines)
    rows = list(csv.reader(io.StringIO("\n".join(ln for ln in lines if not ln.startswith("#")))))
    assert rows[0] == CSV_HEADER and len(rows) > 10
    j = c.get("/api/scorecard/export.json", params={"run_id": run_id})
    assert j.json()["run"]["id"] == run_id
    prov = j.json()["provenance"]
    assert prov["run_id"] == run_id and prov["model"] and prov["prompt_version"] and prov["benchmark_hash"]


def test_scorecard_404s(client):
    c, _ = client
    assert c.get("/api/scorecard", params={"run_id": "nope"}).status_code == 404


def test_scorecard_no_runs():
    r = TestClient(app).get("/api/scorecard")
    assert r.status_code == 404 and "No runs" in r.json()["detail"]
