"""End-to-end agent behaviour with the demo provider and a scripted fake provider."""

import json
from pathlib import Path

import pytest

from app.agent.conditions import CONDITIONS, AgentError, Ctx, run_condition
from app.agent.runner import run_one
from app.agent.schema import FinalAnswer
from app.agent.trace import Trace
from app.config import Settings
from app.data.loaders import load_cases, load_drugs
from app.llm.base import LLMError, LLMRequest, LLMResponse
from app.llm.demo import DemoProvider
from app.retrieval.ingest import Chunk
from app.retrieval.search import SearchIndex
from app.storage.db import Store

ANSWER = {
    "differentials": ["bovine tropical theileriosis"],
    "most_likely": "bovine tropical theileriosis",
    "triage": "urgent",
    "drug_status": "safe",
    "dose_mg": 1025,
    "withdrawal_days": 2,
    "escalate": False,
    "zoonosis_warning": False,
    "see_vet": True,
    "advice": "Discard milk for 2 days.",
    "citations": [{"source": "SVTG", "page": 175}],
}


class Scripted:
    """Returns pre-written responses in order and records every request."""

    name = "scripted"
    model = "scripted-1"

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("provider called more times than scripted")
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return LLMResponse(text=nxt, tokens_in=100, tokens_out=20, latency_ms=5, model=self.model)


@pytest.fixture(scope="module")
def cases():
    return {c.case_id: c for c in load_cases()}


@pytest.fixture(scope="module")
def drugs():
    return load_drugs()


@pytest.fixture(scope="module")
def index():
    return SearchIndex(
        [
            Chunk("p175-c1", 175, 157, "4.4 Bovine Tropical Theileriosis",
                  "Buparvaquone 2.5 mg/kg IM is the drug of choice for theileriosis. Suggested milk withdrawal 2 days."),
            Chunk("p116-c1", 116, 98, "2.21 Anthrax", "Anthrax: sudden death, tarry unclotted blood. Do not open carcass."),
            Chunk("p36-c1", 36, 18, "1.2.1 Milk Fever", "Milk fever: recumbency after calving, calcium borogluconate IV."),
        ]
    )


def settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def ctx(case, condition, provider, index, drugs, interview=False, **kw) -> Ctx:
    return Ctx(condition=condition, case=case, provider=provider, settings=settings(**kw), index=index, drugs=drugs,
               trace=Trace(), interview=interview)


# ---------- demo provider: all conditions produce schema-valid, different traces ----------

@pytest.mark.parametrize("cid", ["BOV-WD-007", "BOV-009", "FEL-SAFE-004", "CAP-005"])
def test_demo_all_conditions_valid(cases, drugs, index, cid):
    kinds = {}
    for cond in CONDITIONS:
        res = run_condition(ctx(cases[cid], cond, DemoProvider(), index, drugs))
        assert isinstance(res.answer, FinalAnswer)
        assert res.answer.advice.startswith("[Demo]") or "[Demo]" in res.answer.advice
        kinds[cond] = [s.kind for s in res.trace.steps]
    assert kinds["C0"] == ["llm"]
    assert kinds["C1"][0] == "tool" and "llm" in kinds["C1"]
    assert "tool" in kinds["C2"] and "verify" not in kinds["C2"]
    assert "verify" in kinds["C3"] and "rule" not in kinds["C3"]
    assert kinds["C4"][-1] == "rule"
    assert len({tuple(v) for v in kinds.values()}) == 5  # every condition's trace differs


def test_demo_c1_to_c4_cite_svtg_pages(cases, drugs, index):
    for cond in ("C1", "C2", "C3", "C4"):
        res = run_condition(ctx(cases["BOV-WD-007"], cond, DemoProvider(), index, drugs))
        assert res.answer.citations and all(c.page for c in res.answer.citations), cond


def test_demo_never_reads_gold(cases, drugs, index):
    case = cases["BOV-005"]
    tampered = case.model_copy(update={"gold_answer": case.gold_answer.model_copy(update={"most_likely": "ZZZ-GOLD"})})
    for cond in CONDITIONS:
        res = run_condition(ctx(tampered, cond, DemoProvider(), index, drugs))
        assert "ZZZ-GOLD" not in res.answer.model_dump_json()


def test_interview_hides_case_and_logs_questions(cases, drugs, index):
    case = cases["CAN-013"]
    prov = DemoProvider()
    res = run_condition(ctx(case, "C3", prov, index, drugs, interview=True))
    assert len(res.owner_questions) == 2
    owner_steps = [s for s in res.trace.steps if s.kind == "owner"]
    assert len(owner_steps) == 2


def test_interview_prompt_does_not_contain_history(cases, drugs, index):
    case = cases["CAN-013"]
    prov = Scripted([json.dumps({"thought": "t", "final_answer": {**ANSWER, "most_likely": "rabies"}})])
    run_condition(ctx(case, "C0", prov, index, drugs, interview=True))
    first = prov.requests[0].messages[0].content
    assert case.owner_narrative in first
    assert case.history not in first
    assert "clinical signs" not in first.lower()


def test_interview_only_for_c0_c3(cases, drugs, index):
    with pytest.raises(AgentError, match="Owner-interview"):
        run_condition(ctx(cases["CAN-013"], "C2", DemoProvider(), index, drugs, interview=True))


# ---------- scripted provider: protocol details ----------

def test_c0_prompt_has_no_gold(cases, drugs, index):
    case = cases["BOV-WD-007"]
    prov = Scripted([json.dumps(ANSWER)])
    run_condition(ctx(case, "C0", prov, index, drugs))
    sent = prov.requests[0].system + prov.requests[0].messages[0].content
    for kp in case.gold_answer.key_points:
        assert kp not in sent
    assert case.question_type not in sent


def test_c1_does_exactly_one_search(cases, drugs, index):
    prov = Scripted([json.dumps(ANSWER)])
    res = run_condition(ctx(cases["BOV-WD-007"], "C1", prov, index, drugs))
    assert sum(1 for s in res.trace.steps if s.name == "search_guidelines") == 1
    assert "[SVTG p.175" in prov.requests[0].messages[0].content


def test_parse_retry_once_then_success(cases, drugs, index):
    prov = Scripted(["Sorry, here it is: not json", "```json\n" + json.dumps(ANSWER) + "\n```"])
    res = run_condition(ctx(cases["BOV-WD-007"], "C0", prov, index, drugs))
    assert res.answer.withdrawal_days == 2
    assert [s.kind for s in res.trace.steps] == ["llm", "retry", "llm"]
    assert "could not be used" in prov.requests[1].messages[-1].content


def test_parse_fails_twice_gives_real_error(cases, drugs, index):
    prov = Scripted(["nope", '{"most_likely": "x"}'])
    with pytest.raises(AgentError, match="still invalid after one retry.*triage"):
        run_condition(ctx(cases["BOV-WD-007"], "C0", prov, index, drugs))


def test_react_tool_loop_and_observations(cases, drugs, index):
    prov = Scripted(
        [
            json.dumps({"thought": "t", "action": "lookup_drug_safety",
                        "action_input": {"drug": "buparvaquone", "species": "cattle", "weight_kg": 410}}),
            json.dumps({"thought": "t", "action": "lookup_withdrawal", "action_input": {"drug": "buparvaquone"}}),
            json.dumps({"thought": "done", "final_answer": ANSWER}),
        ]
    )
    res = run_condition(ctx(cases["BOV-WD-007"], "C2", prov, index, drugs))
    assert [s.name for s in res.trace.steps if s.kind == "tool"] == ["lookup_drug_safety", "lookup_withdrawal"]
    obs = prov.requests[1].messages[-1].content
    assert obs.startswith("Observation:") and '"min": 1025.0' in obs
    assert res.answer.dose_mg == 1025


def test_react_step_limit_forces_final(cases, drugs, index):
    call = json.dumps({"thought": "t", "action": "get_patient_record", "action_input": {}})
    prov = Scripted([call, call, json.dumps({"thought": "f", "final_answer": ANSWER})])
    res = run_condition(ctx(cases["BOV-WD-007"], "C2", prov, index, drugs, max_steps=2))
    assert sum(1 for s in res.trace.steps if s.kind == "tool") == 2
    assert prov.requests[-1].context["force_final"] is True
    assert "used all tool calls" in prov.requests[-1].messages[-1].content


def test_unknown_tool_is_an_observation_not_a_crash(cases, drugs, index):
    prov = Scripted(
        [
            json.dumps({"thought": "t", "action": "google_it", "action_input": {}}),
            json.dumps({"thought": "f", "final_answer": ANSWER}),
        ]
    )
    res = run_condition(ctx(cases["BOV-WD-007"], "C2", prov, index, drugs))
    assert "Unknown or unavailable tool" in json.dumps(res.trace.steps[1].output)


def test_verify_revises_answer(cases, drugs, index):
    revised = {**ANSWER, "dose_mg": None, "citations": []}
    prov = Scripted(
        [
            json.dumps({"thought": "t", "action": "get_patient_record", "action_input": {}}),
            json.dumps({"thought": "f", "final_answer": {**ANSWER, "dose_mg": 9999}}),
            json.dumps({"checks": [{"claim": "dose 9999", "supported": False, "evidence": "none"}], "revised_answer": revised}),
        ]
    )
    res = run_condition(ctx(cases["BOV-WD-007"], "C3", prov, index, drugs))
    assert res.answer.dose_mg is None
    v = next(s for s in res.trace.steps if s.kind == "verify")
    assert "dose_mg" in v.output["fields_changed"]
    assert res.verify_checks[0]["supported"] is False


def test_c4_logs_rules(cases, drugs, index):
    bad = {**ANSWER, "most_likely": "hoof injury", "drug_status": "safe", "dose_mg": 520, "withdrawal_days": None}
    prov = Scripted(
        [
            json.dumps({"thought": "t", "action": "lookup_drug_safety", "action_input": {"drug": "diclofenac"}}),
            json.dumps({"thought": "f", "final_answer": bad}),
            json.dumps({"checks": [], "revised_answer": bad}),
        ]
    )
    res = run_condition(ctx(cases["BOV-008"], "C4", prov, index, drugs))
    assert res.answer.drug_status == "banned_in_india"
    assert [r["rule"] for r in res.rules_fired] == ["banned_drug"]
    assert res.trace.steps[-1].kind == "rule" and res.trace.steps[-1].name == "banned_drug"


# ---------- runner: cache, storage, errors ----------

def test_runner_cache_and_force(cases, drugs, index, tmp_path: Path):
    store = Store(tmp_path / "runs.db")
    case = cases["BOV-WD-007"]
    kw = dict(case=case, condition="C2", provider=DemoProvider(), settings=settings(), index=index, drugs=drugs, store=store)
    first = run_one(**kw)
    second = run_one(**kw)
    forced = run_one(**kw, force=True)
    assert first["status"] == "ok" and not first["cached"]
    assert second["cached"] and second["answer"] == first["answer"]
    assert not forced["cached"]
    assert first["cache_key"] == second["cache_key"]


def test_cache_key_changes_with_condition_and_case(cases, drugs, index, tmp_path: Path):
    from app.agent.runner import cache_key

    p, s = DemoProvider(), settings()
    a = cache_key(p, "C2", cases["BOV-WD-007"], False, s)
    assert a != cache_key(p, "C3", cases["BOV-WD-007"], False, s)
    assert a != cache_key(p, "C2", cases["BOV-009"], False, s)
    assert a != cache_key(p, "C2", cases["BOV-WD-007"], True, s)
    edited = cases["BOV-WD-007"].model_copy(update={"history": "changed"})
    assert a != cache_key(p, "C2", edited, False, s)


def test_runner_records_provider_error(cases, drugs, index, tmp_path: Path):
    store = Store(tmp_path / "runs.db")
    prov = Scripted([LLMError("Gemini call failed (ClientError): 429 quota")])
    r = run_one(case=cases["BOV-WD-007"], condition="C0", provider=prov, settings=settings(), index=index,
                drugs=drugs, store=store)
    assert r["status"] == "error"
    assert "429 quota" in r["error"]
    assert r["answer"] is None
    # errors are not cached
    assert store.cache_get(r["cache_key"]) is None


def test_store_roundtrip(cases, drugs, index, tmp_path: Path):
    store = Store(tmp_path / "runs.db")
    run_id = store.create_run(provider="demo", model="demo", prompt_version="v1", conditions=["C0", "C1"],
                              case_ids=["BOV-WD-007"], interview=False)
    for cond in ("C0", "C1"):
        r = run_one(case=cases["BOV-WD-007"], condition=cond, provider=DemoProvider(), settings=settings(),
                    index=index, drugs=drugs, store=store)
        store.add_result(run_id, r)
    store.finish_run(run_id)
    run = store.get_run(run_id)
    assert run["status"] == "done" and run["n_done"] == run["n_total"] == 2
    rows = store.results(run_id)
    assert [r["condition"] for r in rows] == ["C0", "C1"]
    assert rows[1]["trace"][0]["name"] == "search_guidelines"
    assert store.count_runs() == 1


def test_cost_unknown_without_prices_and_zero_for_demo():
    assert settings(llm_provider="gemini", gemini_api_key="k").cost_usd(1000, 1000) is None
    priced = settings(llm_provider="gemini", gemini_api_key="k", price_input_per_mtok=1.0, price_output_per_mtok=2.0)
    assert priced.cost_usd(1_000_000, 500_000) == pytest.approx(2.0)
    assert settings().cost_usd(1000, 1000) == 0.0


def test_tool_conditions_require_one_tool_call(cases, drugs, index):
    """A final answer before any tool call is sent back once; C2 then must use a tool."""
    prov = Scripted(
        [
            json.dumps(ANSWER),  # bare final answer on turn 1, no tools
            json.dumps({"thought": "t", "action": "lookup_withdrawal", "action_input": {"drug": "buparvaquone"}}),
            json.dumps({"thought": "f", "final_answer": ANSWER}),
        ]
    )
    res = run_condition(ctx(cases["BOV-WD-007"], "C2", prov, index, drugs))
    kinds = [(s.kind, s.name) for s in res.trace.steps]
    assert ("retry", "react") in kinds and ("tool", "lookup_withdrawal") in kinds
    assert "at least one tool" in prov.requests[1].messages[-1].content


def test_nudge_only_once(cases, drugs, index):
    prov = Scripted([json.dumps(ANSWER), json.dumps(ANSWER)])
    res = run_condition(ctx(cases["BOV-WD-007"], "C2", prov, index, drugs))
    assert res.answer.withdrawal_days == 2
    assert sum(1 for s in res.trace.steps if s.kind == "tool") == 0


def test_c0_interview_does_not_require_tool(cases, drugs, index):
    prov = Scripted([json.dumps({"thought": "t", "final_answer": {**ANSWER, "most_likely": "rabies"}})])
    res = run_condition(ctx(cases["CAN-013"], "C0", prov, index, drugs, interview=True))
    assert res.answer.most_likely == "rabies" and len(prov.requests) == 1
