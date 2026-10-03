"""Demo provider: scripted sample responses when no API key is configured.

It never reads the gold answer. It builds answers only from what the agent has
in front of it (case text, retrieved passages, tool results), using simple
heuristics, so demo results are illustrative and not a model's output. Every
advice string starts with "[Demo]".
"""

import json
import re
import time
from typing import Any

from app.agent.guardrails import load_seed, red_flags_in
from app.data.loaders import DataError, load_drugs
from app.llm.base import LLMRequest, LLMResponse, estimate_tokens
from app.tools.drugs import detect_drugs

WITHDRAWAL_WORDS = re.compile(r"withdraw|withheld|sell|selling|milk|meat|lift the birds|trader", re.I)
INTERVIEW_QUESTIONS = [
    "How old is the animal, roughly how heavy, and is it pregnant or giving milk?",
    "What changes have you noticed, since when, and has anything been given or changed recently?",
]


def _drug_rows():
    try:
        return load_drugs()
    except DataError:
        return []


def _case_text(view: dict[str, Any]) -> str:
    return " ".join(
        str(view.get(k, "")) for k in ("history", "owner_narrative", "question")
    ) + " " + " ".join(view.get("clinical_signs", []))


def _section_name(section: str) -> str:
    name = re.sub(r"^\d+(?:[.\-]\d+)*\s*", "", section).strip()
    name = re.sub(r"\s*\(.*?\)\s*$", "", name)
    return name or "unclear"


def _triage(view: dict[str, Any]) -> str:
    flags = red_flags_in(load_seed(), _case_text(view))
    if any(f.min_triage == "emergency" for f in flags):
        return "emergency"
    return "urgent" if flags else "routine"


def synth_answer(
    view: dict[str, Any],
    passages: list[dict[str, Any]],
    lookups: list[tuple[str, dict[str, Any], dict[str, Any]]],
    label: str,
) -> dict[str, Any]:
    sections: list[str] = []
    for p in passages:
        name = _section_name(p.get("section", ""))
        if name not in sections and "preamble" not in name.lower() and "annexure" not in name.lower():
            sections.append(name)
    most_likely = sections[0] if sections else "undetermined without examination"
    triage = _triage(view)

    drug_status, dose, withdrawal = "n/a", None, None
    for tool, _args, result in lookups:
        if tool == "lookup_drug_safety":
            status = result.get("status")
            drug_status = status if status in ("safe", "contraindicated", "banned_in_india") else "n/a"
            total = result.get("dose_mg_total")
            if drug_status == "safe" and total:
                dose = total["min"]
        if tool == "lookup_withdrawal" and result.get("known"):
            milk = view.get("signalment", {}).get("lactating")
            withdrawal = result.get("milk_withdrawal_days") if milk else result.get("meat_withdrawal_days")
            withdrawal = withdrawal if withdrawal is not None else result.get("meat_withdrawal_days")

    pages = []
    for p in passages:
        if p["page"] not in pages:
            pages.append(p["page"])
    advice = (
        f"[Demo] {label} sample response, not live model output. "
        f"Leading consideration: {most_likely}. Please have a veterinarian examine the animal."
    )
    if drug_status in ("banned_in_india", "contraindicated"):
        advice += " Do not give the drug you asked about."
    return {
        "differentials": sections[:4],
        "most_likely": most_likely,
        "triage": triage,
        "drug_status": drug_status,
        "dose_mg": dose,
        "withdrawal_days": withdrawal,
        "escalate": triage == "emergency",
        "zoonosis_warning": False,
        "see_vet": True,
        "advice": advice,
        "citations": [{"source": "SVTG", "page": pg} for pg in pages[:3]],
    }


class DemoProvider:
    name = "demo"
    model = "demo"

    def __init__(self, delay_ms: int = 0):
        self.delay_ms = delay_ms

    def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        handler = {
            "answer": self._answer,
            "react": self._react,
            "verify": self._verify,
            "owner": self._owner,
        }[request.task]
        text = handler(request.context)
        prompt = request.system + "".join(m.content for m in request.messages)
        return LLMResponse(
            text=text,
            tokens_in=estimate_tokens(prompt),
            tokens_out=estimate_tokens(text),
            latency_ms=int((time.perf_counter() - start) * 1000),
            model=self.model,
            tokens_estimated=True,
        )

    # C0 / C1
    def _answer(self, ctx: dict[str, Any]) -> str:
        view = ctx["case"]
        if ctx.get("condition") == "C0":
            ans = synth_answer(view, [], [], "C0 bare-model")
            ans["differentials"] = []
            return json.dumps(ans)
        return "```json\n" + json.dumps(synth_answer(view, ctx.get("passages", []), [], "C1 retrieval")) + "\n```"

    # C2 / C3 ReAct steps
    def _react(self, ctx: dict[str, Any]) -> str:
        view = ctx["case"]
        steps: list[dict[str, Any]] = ctx.get("steps", [])
        done = [s["action"] for s in steps]
        interview = ctx.get("interview", False)
        text = _case_text(view)
        drugs = detect_drugs(_drug_rows(), text)
        weight = view.get("signalment", {}).get("weight_kg")

        tools = set(ctx.get("tools", []))

        def act(thought: str, action: str, args: dict[str, Any]) -> str:
            return json.dumps({"thought": f"[Demo] {thought}", "action": action, "action_input": args})

        if not ctx.get("force_final"):
            if "ask_owner" in tools:
                asked = done.count("ask_owner")
                if asked < len(INTERVIEW_QUESTIONS):
                    return act("Need more history from the owner.", "ask_owner", {"question": INTERVIEW_QUESTIONS[asked]})
            if "get_patient_record" in tools and "get_patient_record" not in done:
                return act("Read the patient record first.", "get_patient_record", {})
            if "search_guidelines" in tools and "search_guidelines" not in done:
                if interview:
                    replies = " ".join(
                        s["result"].get("owner_reply", "") for s in steps if s["action"] == "ask_owner"
                    )
                    basis = f"{view.get('owner_narrative', '')} {replies}"[:400]
                else:
                    basis = f"{view.get('history', '')} {' '.join(view.get('clinical_signs', []))}"
                return act("Search the SVTG for this history and these signs.", "search_guidelines",
                           {"query": f"{view['species']} {basis}"})
            if drugs and "lookup_drug_safety" in tools and "lookup_drug_safety" not in done:
                args: dict[str, Any] = {"drug": drugs[0], "species": view["species"]}
                if weight:
                    args["weight_kg"] = weight
                return act(f"Check {drugs[0]} in the drug table.", "lookup_drug_safety", args)
            if (
                drugs
                and "lookup_withdrawal" in tools
                and WITHDRAWAL_WORDS.search(view.get("question", ""))
                and "lookup_withdrawal" not in done
            ):
                return act("Check the withdrawal period.", "lookup_withdrawal", {"drug": drugs[0], "species": view["species"]})

        passages = [p for s in steps if s["action"] == "search_guidelines" for p in s["result"].get("passages", [])]
        lookups = [(s["action"], s["input"], s["result"]) for s in steps if s["action"].startswith("lookup_")]
        label = ctx.get("label", "C2 tools")
        answer = synth_answer(view, passages, lookups, label)
        return json.dumps({"thought": "[Demo] Enough evidence to answer.", "final_answer": answer})

    # C3 verification pass
    def _verify(self, ctx: dict[str, Any]) -> str:
        draft = dict(ctx["draft"])
        evidence = ctx.get("evidence", [])
        ev_text = json.dumps(evidence).lower()
        pages = {p["page"] for e in evidence for p in e.get("result", {}).get("passages", [])}
        checks = []

        dx_supported = draft["most_likely"].lower() in ev_text
        checks.append({"claim": f"most likely: {draft['most_likely']}", "supported": dx_supported, "evidence": "search results"})
        if draft.get("dose_mg") is not None:
            ok = any(
                e.get("result", {}).get("dose_mg_total", {}) and e["result"]["dose_mg_total"]["min"] <= draft["dose_mg"] <= e["result"]["dose_mg_total"]["max"]
                for e in evidence
            )
            checks.append({"claim": f"dose {draft['dose_mg']} mg", "supported": ok, "evidence": "lookup_drug_safety"})
            if not ok:
                draft["dose_mg"] = None
        if draft.get("withdrawal_days") is not None:
            ok = any(e.get("result", {}).get("known") for e in evidence)
            checks.append({"claim": f"withdrawal {draft['withdrawal_days']} days", "supported": ok, "evidence": "lookup_withdrawal"})
            if not ok:
                draft["withdrawal_days"] = None
        kept = [c for c in draft.get("citations", []) if c.get("page") in pages]
        if len(kept) != len(draft.get("citations", [])):
            checks.append({"claim": "citations", "supported": False, "evidence": "dropped pages not in evidence"})
        draft["citations"] = kept
        draft["advice"] = draft["advice"].replace("C2 tools sample", "C3 self-verified sample")
        return json.dumps({"checks": checks, "revised_answer": draft})

    # Owner simulator
    def _owner(self, ctx: dict[str, Any]) -> str:
        facts = ctx["facts"]
        q = ctx["question"].lower()
        s = facts.get("signalment", {})
        parts = []
        if re.search(r"old|age|heavy|weigh|pregnan|milk|lactat", q):
            sex = s.get("sex", "").replace("_", " ")
            milk = " She is giving milk." if s.get("lactating") else ""
            parts.append(f"It's a {s.get('breed', '')} {sex}, about {s.get('age_months')} months old and around {s.get('weight_kg')} kg.{milk}")
        if re.search(r"notic|sign|change|since|when|given|happen|symptom", q):
            parts.append(facts.get("history", ""))
            signs = facts.get("clinical_signs", [])
            if signs:
                parts.append("I have seen: " + ", ".join(signs[:4]) + ".")
        return " ".join(p for p in parts if p) or "I'm not sure, I haven't noticed that."
