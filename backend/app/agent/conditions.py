"""The five conditions. All return the same FinalAnswer schema.

C0 bare LLM · C1 one SVTG search · C2 ReAct tools (≤ max_steps) · C3 C2 + self-verify · C4 C3 + guardrails.
Owner-interview mode (C0, C3): the case is hidden; the agent sees only the species, the owner's words and
question, and must ask the owner simulator for anything else.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Literal, TypeVar

from app.agent import prompts
from app.agent.guardrails import apply_guardrails
from app.agent.parser import ParseError, extract_json, parse_action, parse_final_answer
from app.agent.schema import FinalAnswer
from app.agent.trace import Trace, clip
from app.config import Settings
from app.data.models import Case, DrugRow
from app.llm.base import LLMRequest, Message, Provider
from app.retrieval.search import SearchIndex
from app.tools.registry import Toolbox, case_view

ConditionId = Literal["C0", "C1", "C2", "C3", "C4"]
CONDITIONS: tuple[ConditionId, ...] = ("C0", "C1", "C2", "C3", "C4")
INTERVIEW_CONDITIONS: tuple[ConditionId, ...] = ("C0", "C3")
C2_TOOLS = ("search_guidelines", "lookup_drug_safety", "lookup_withdrawal", "get_patient_record")
C3_INTERVIEW_TOOLS = ("search_guidelines", "lookup_drug_safety", "lookup_withdrawal", "ask_owner")

T = TypeVar("T")


class AgentError(Exception):
    """The condition could not produce a valid answer. Message is shown to the user."""


@dataclass
class AgentResult:
    answer: FinalAnswer
    trace: Trace
    rules_fired: list[dict[str, Any]] = field(default_factory=list)
    owner_questions: list[str] = field(default_factory=list)
    verify_checks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Ctx:
    condition: ConditionId
    case: Case
    provider: Provider
    settings: Settings
    index: SearchIndex
    drugs: list[DrugRow]
    trace: Trace
    interview: bool = False

    @property
    def view(self) -> dict[str, Any]:
        v = case_view(self.case)
        if self.interview:
            return {k: v[k] for k in ("case_id", "species", "owner_narrative", "question")}
        return v


def _last_user(messages: list[Message]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


def llm_json(ctx: Ctx, req: LLMRequest, parse: Callable[[str], T], name: str) -> tuple[T, str]:
    """Call the model, parse its JSON; on failure send the error back and retry once."""
    req = replace(req, temperature=ctx.settings.temperature)
    resp = ctx.provider.complete(req)
    ctx.trace.add(
        "llm", name,
        input={"messages": len(req.messages), "last": clip(_last_user(req.messages), 1500)},
        output=clip(resp.text),
        latency_ms=resp.latency_ms, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
        note="tokens estimated" if resp.tokens_estimated else "",
    )
    try:
        return parse(resp.text), resp.text
    except ParseError as first:
        ctx.trace.add("retry", name, output=str(first), note="sending parse error back to the model (1 retry)")
        retry = replace(
            req,
            messages=[*req.messages, Message("assistant", resp.text), Message("user", prompts.REPAIR.format(error=first))],
        )
        resp2 = ctx.provider.complete(retry)
        ctx.trace.add(
            "llm", f"{name} (retry)",
            input={"messages": len(retry.messages), "last": prompts.REPAIR.format(error=first)},
            output=clip(resp2.text),
            latency_ms=resp2.latency_ms, tokens_in=resp2.tokens_in, tokens_out=resp2.tokens_out,
            note="tokens estimated" if resp2.tokens_estimated else "",
        )
        try:
            return parse(resp2.text), resp2.text
        except ParseError as second:
            raise AgentError(f"{name}: model output still invalid after one retry — {second}") from None


def _toolbox(ctx: Ctx, allowed: tuple[str, ...]) -> Toolbox:
    box = Toolbox(case=ctx.case, index=ctx.index, drugs=ctx.drugs, allowed=allowed)
    if "ask_owner" in allowed:
        box.ask_owner_fn = lambda q: ask_owner(ctx, box, q)
    return box


def ask_owner(ctx: Ctx, box: Toolbox, question: str) -> str:
    if len(box.owner_questions) > ctx.settings.max_owner_questions:
        return "(The owner has no time for more questions.)"
    full = case_view(ctx.case)
    facts = {k: full[k] for k in ("species", "signalment", "history", "owner_narrative", "clinical_signs")}
    req = LLMRequest(
        system=prompts.OWNER_SYSTEM,
        messages=[Message("user", prompts.owner_user(facts, question))],
        json_mode=False,
        task="owner",
        context={"facts": facts, "question": question},
        temperature=ctx.settings.temperature,
    )
    resp = ctx.provider.complete(req)
    ctx.trace.add(
        "owner", "owner_simulator", input=question, output=resp.text.strip(),
        latency_ms=resp.latency_ms, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
        note="tokens estimated" if resp.tokens_estimated else "",
    )
    return resp.text.strip()


# ---------- C0 ----------
def run_c0(ctx: Ctx) -> AgentResult:
    if ctx.interview:
        box = _toolbox(ctx, ("ask_owner",))
        answer, _ = _react(ctx, box, ctx.settings.max_owner_questions, "C0 interview")
        return AgentResult(answer, ctx.trace, owner_questions=box.owner_questions)
    req = LLMRequest(
        system=prompts.C0_SYSTEM,
        messages=[Message("user", prompts.c0_user(ctx.view))],
        task="answer",
        context={"condition": "C0", "case": ctx.view},
    )
    answer, _ = llm_json(ctx, req, parse_final_answer, "answer")
    return AgentResult(answer, ctx.trace)


# ---------- C1 ----------
def run_c1(ctx: Ctx) -> AgentResult:
    box = _toolbox(ctx, ("search_guidelines",))
    query = prompts.c1_query(ctx.view)
    t = time.perf_counter()
    passages = box.search(query, 5)
    ctx.trace.add(
        "tool", "search_guidelines",
        input={"query": query, "k": 5},
        output={"pages": [p["page"] for p in passages], "sections": [p["section"] for p in passages]},
        latency_ms=int((time.perf_counter() - t) * 1000),
        note="single retrieval (C1)",
    )
    req = LLMRequest(
        system=prompts.C1_SYSTEM,
        messages=[Message("user", prompts.c1_user(ctx.view, passages))],
        task="answer",
        context={"condition": "C1", "case": ctx.view, "passages": passages},
    )
    answer, _ = llm_json(ctx, req, parse_final_answer, "answer")
    return AgentResult(answer, ctx.trace)


# ---------- ReAct (C2, C3, interview) ----------
def _parse_step(text: str) -> dict[str, Any]:
    step = parse_action(text)
    if "final_answer" in step:
        step["final_answer"] = parse_final_answer(step["final_answer"])
    return step


def _parse_final_step(text: str) -> dict[str, Any]:
    step = _parse_step(text)
    if "final_answer" not in step:
        raise ParseError("a final_answer is required now (no more tool calls)")
    return step


def _summarise_result(result: dict[str, Any]) -> Any:
    if "passages" in result:
        return {
            "query": result.get("query"),
            "passages": [{"page": p["page"], "section": p["section"], "text": clip(p["text"], 300)} for p in result["passages"]],
        }
    return result


def _react(ctx: Ctx, box: Toolbox, max_steps: int, label: str) -> tuple[FinalAnswer, list[dict[str, Any]]]:
    system = prompts.react_system(box.specs_text(), max_steps)
    messages = [Message("user", prompts.react_user(ctx.view, ctx.interview))]
    steps: list[dict[str, Any]] = []

    def request(force: bool) -> LLMRequest:
        return LLMRequest(
            system=system,
            messages=list(messages),
            task="react",
            context={
                "case": ctx.view, "interview": ctx.interview, "steps": steps, "label": label,
                "force_final": force, "tools": list(box.allowed),
            },
        )

    for _ in range(max_steps):
        step, raw = llm_json(ctx, request(False), _parse_step, "react")
        if "final_answer" in step:
            return step["final_answer"], steps
        messages.append(Message("assistant", raw))
        name, args = step["action"], step["action_input"]
        t = time.perf_counter()
        result = box.call(name, args)
        if name != "ask_owner":  # the owner simulator records its own step
            ctx.trace.add(
                "tool", name, input=args, output=_summarise_result(result),
                latency_ms=int((time.perf_counter() - t) * 1000),
                note=step.get("thought", "")[:300] if isinstance(step.get("thought"), str) else "",
            )
        steps.append({"action": name, "input": args, "result": result})
        messages.append(Message("user", prompts.observation(result)))

    messages.append(Message("user", prompts.FORCE_FINAL))
    step, _ = llm_json(ctx, request(True), _parse_final_step, "react (final)")
    return step["final_answer"], steps


def run_c2(ctx: Ctx) -> AgentResult:
    box = _toolbox(ctx, C2_TOOLS)
    answer, _ = _react(ctx, box, ctx.settings.max_steps, "C2 tools")
    return AgentResult(answer, ctx.trace)


# ---------- C3 ----------
def _verify(ctx: Ctx, draft: FinalAnswer, evidence: list[dict[str, Any]]) -> tuple[FinalAnswer, list[dict[str, Any]]]:
    compact = [{"action": e["action"], "input": e["input"], "result": e["result"]} for e in evidence]
    draft_d = draft.model_dump()
    req = LLMRequest(
        system=prompts.VERIFY_SYSTEM,
        messages=[Message("user", prompts.verify_user(ctx.view, draft_d, compact, ctx.interview))],
        task="verify",
        context={"case": ctx.view, "draft": draft_d, "evidence": compact},
    )

    def parse(text: str) -> tuple[FinalAnswer, list[dict[str, Any]]]:
        obj = extract_json(text)
        checks = obj.get("checks") if isinstance(obj.get("checks"), list) else []
        revised = obj.get("revised_answer")
        if not isinstance(revised, dict):
            raise ParseError('verification reply needs a "revised_answer" object')
        return parse_final_answer(revised), checks

    (revised, checks), _ = llm_json(ctx, req, parse, "verify")
    changed = [k for k, v in revised.model_dump().items() if draft_d.get(k) != v]
    ctx.trace.add(
        "verify", "self_verify",
        input={"claims_checked": len(checks)},
        output={"unsupported": [c for c in checks if isinstance(c, dict) and c.get("supported") is False], "fields_changed": changed},
    )
    return revised, checks


def run_c3(ctx: Ctx) -> AgentResult:
    if ctx.interview:
        box = _toolbox(ctx, C3_INTERVIEW_TOOLS)
        budget = ctx.settings.max_steps + ctx.settings.max_owner_questions
        draft, evidence = _react(ctx, box, budget, "C3 interview")
    else:
        box = _toolbox(ctx, C2_TOOLS)
        draft, evidence = _react(ctx, box, ctx.settings.max_steps, "C2 tools")
    revised, checks = _verify(ctx, draft, evidence)
    return AgentResult(revised, ctx.trace, owner_questions=box.owner_questions, verify_checks=checks)


# ---------- C4 ----------
def run_c4(ctx: Ctx) -> AgentResult:
    base = run_c3(ctx)
    final, fired = apply_guardrails(base.answer, ctx.case, ctx.drugs)
    for f in fired:
        ctx.trace.add("rule", f.rule, input=f.detail, output=f.changes)
    if not fired:
        ctx.trace.add("rule", "no_rules_fired", output={}, note="guardrails checked; nothing changed")
    base.answer = final
    base.rules_fired = [f.to_dict() for f in fired]
    return base


RUNNERS: dict[ConditionId, Callable[[Ctx], AgentResult]] = {
    "C0": run_c0, "C1": run_c1, "C2": run_c2, "C3": run_c3, "C4": run_c4,
}


def run_condition(ctx: Ctx) -> AgentResult:
    if ctx.interview and ctx.condition not in INTERVIEW_CONDITIONS:
        raise AgentError(f"Owner-interview mode is only defined for {', '.join(INTERVIEW_CONDITIONS)}")
    return RUNNERS[ctx.condition](ctx)
