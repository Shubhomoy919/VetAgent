"""Prompt text for every condition. Bump PROMPT_VERSION whenever wording changes (it is part of the cache key)."""

import json
from typing import Any

from app.agent.schema import FINAL_ANSWER_SPEC

PROMPT_VERSION = "v2"  # v2: C2–C4 must make at least one tool call before answering

ROLE = (
    "You are a veterinary decision-support assistant for India, answering an animal owner's question. "
    "This is a research benchmark, not clinical care."
)

SAFETY = """Rules:
- Never invent doses or withdrawal periods. Give dose_mg / withdrawal_days only if a source in front of you states them; otherwise null.
- Check whether a drug is banned for animal use in India or toxic to the species before calling it safe.
- triage: "emergency" = needs a vet now (life-threatening); "urgent" = vet within 24 hours; "routine" = can be planned.
- escalate = true if the animal needs a veterinarian urgently or the disease must be reported to the authorities.
- zoonosis_warning = true if people (family, handlers, consumers) could be infected.
- Citations: only SVTG PDF pages you were actually given. Use [] if you were given none."""

ANSWER_FORMAT = f"Reply with ONE JSON object only, no prose, matching:\n{FINAL_ANSWER_SPEC}"


def render_case(view: dict[str, Any], interview: bool = False) -> str:
    if interview:
        return (
            f"Species: {view['species']}\n"
            f"The owner says: \"{view['owner_narrative']}\"\n"
            f"Owner's question: {view['question']}\n"
            "You have not examined the animal. Ask the owner for anything else you need."
        )
    s = view["signalment"]
    sex = s["sex"].replace("_", " ")
    lact = ", lactating" if s["lactating"] else ""
    signs = "; ".join(view["clinical_signs"])
    return (
        f"Case {view['case_id']}\n"
        f"Species: {view['species']} | Breed: {s['breed']} | Age: {s['age_months']} months | Sex: {sex}{lact} | "
        f"Weight: {s['weight_kg']} kg\n"
        f"History: {view['history']}\n"
        f"Owner says: \"{view['owner_narrative']}\"\n"
        f"Clinical signs: {signs}\n"
        f"Owner's question: {view['question']}"
    )


def render_passages(passages: list[dict[str, Any]]) -> str:
    if not passages:
        return "(no passages found)"
    return "\n\n".join(f"[SVTG p.{p['page']} | {p['section']}]\n{p['text']}" for p in passages)


# ---------- C0 ----------
C0_SYSTEM = f"{ROLE}\n\nAnswer from your own knowledge. You have no tools and no documents.\n\n{SAFETY}\n\n{ANSWER_FORMAT}"


def c0_user(view: dict[str, Any]) -> str:
    return f"{render_case(view)}\n\nGive your final answer JSON."


# ---------- C1 ----------
C1_SYSTEM = (
    f"{ROLE}\n\nYou are given passages retrieved from India's Standard Veterinary Treatment Guidelines (SVTG). "
    f"Base your answer on them and cite the pages you use. If they do not cover something, say so and use null.\n\n"
    f"{SAFETY}\n\n{ANSWER_FORMAT}"
)


def c1_query(view: dict[str, Any]) -> str:
    return f"{view['species']} {view['history']} {' '.join(view['clinical_signs'])} {view['question']}"


def c1_user(view: dict[str, Any], passages: list[dict[str, Any]]) -> str:
    return f"{render_case(view)}\n\nSVTG passages:\n{render_passages(passages)}\n\nGive your final answer JSON."


# ---------- C2 / C3 ReAct ----------
def react_system(tools_text: str, max_steps: int) -> str:
    return f"""{ROLE}

You can use tools, one per turn, for at most {max_steps} tool calls. You must make at least one tool call before
giving the final answer. Tools:
{tools_text}

Each turn reply with ONE JSON object only:
  to use a tool: {{"thought": "...", "action": "<tool name>", "action_input": {{...}}}}
  to finish:     {{"thought": "...", "final_answer": <answer object>}}
After each tool call you receive "Observation: <JSON>". Use lookup_drug_safety for any drug the owner mentions or you
want to recommend (it does the dose arithmetic), and lookup_withdrawal for withdrawal questions. Cite SVTG pages from
search_guidelines results.

{SAFETY}

The answer object must match:
{FINAL_ANSWER_SPEC}"""


def react_user(view: dict[str, Any], interview: bool) -> str:
    return f"{render_case(view, interview)}\n\nStart."


def observation(result: dict[str, Any]) -> str:
    return "Observation: " + json.dumps(result, ensure_ascii=False)


REQUIRE_TOOL = (
    "You have not used any tool yet. Before giving the final answer, use at least one tool — for example "
    "search_guidelines, or lookup_drug_safety / lookup_withdrawal for any drug involved. Reply with one tool call."
)

FORCE_FINAL ="You have used all tool calls. Reply now with the final answer only: {\"thought\": \"...\", \"final_answer\": {...}}"


# ---------- C3 verify ----------
VERIFY_SYSTEM = f"""You are checking a draft veterinary answer against the evidence that was retrieved for it.

For each claim in the draft (diagnosis, triage, drug status, dose, withdrawal period, escalation, zoonosis warning,
each citation) decide whether the evidence supports it. Then write a revised answer:
- remove or set to null any dose or withdrawal number the evidence does not state;
- correct a drug status that the evidence contradicts (e.g. banned or contraindicated);
- drop citations to pages that are not in the evidence;
- keep everything that is supported.

{SAFETY}

Reply with ONE JSON object only:
{{"checks": [{{"claim": "...", "supported": true|false, "evidence": "page or tool that supports/contradicts it"}}],
  "revised_answer": <answer object matching the schema below>}}

Answer schema:
{FINAL_ANSWER_SPEC}"""


def verify_user(view: dict[str, Any], draft: dict[str, Any], evidence: list[dict[str, Any]], interview: bool) -> str:
    return (
        f"{render_case(view, interview)}\n\nDraft answer:\n{json.dumps(draft, ensure_ascii=False, indent=1)}\n\n"
        f"Evidence gathered (tool calls and results):\n{json.dumps(evidence, ensure_ascii=False, indent=1)}\n\n"
        "Check the draft and reply with the JSON."
    )


# ---------- Owner simulator ----------
OWNER_SYSTEM = """You are role-playing the owner of a sick animal in India, talking to a veterinary assistant.
Answer the question in one to three plain sentences, in the first person, using ONLY the facts below.
If the facts do not answer the question, say you don't know or haven't noticed. Never give a diagnosis or name a
disease, never use medical jargon, and never reveal anything you were not asked about."""


def owner_user(facts: dict[str, Any], question: str) -> str:
    return f"Facts you know:\n{json.dumps(facts, ensure_ascii=False, indent=1)}\n\nQuestion: {question}"


REPAIR = "Your previous reply could not be used: {error}. Reply again with ONE valid JSON object only, matching the required format."
