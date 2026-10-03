"""The agent's tools and their prompt descriptions."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.data.models import Case, DrugRow
from app.retrieval.search import SearchIndex
from app.tools.drugs import lookup_drug_safety, lookup_withdrawal

TOOL_SPECS: dict[str, dict[str, Any]] = {
    "search_guidelines": {
        "description": "Search India's Standard Veterinary Treatment Guidelines (SVTG). Returns passages with PDF page numbers.",
        "args": {"query": "string", "k": "integer, optional, default 4 (max 6)"},
    },
    "lookup_drug_safety": {
        "description": "Check a drug for a species in the curated drug table: status (safe / contraindicated / "
        "banned_in_india / unknown), legality in India, dose range and the total dose computed for the weight.",
        "args": {"drug": "string", "species": "string", "weight_kg": "number, optional"},
    },
    "lookup_withdrawal": {
        "description": "Milk and meat withdrawal periods for a drug in a species, if a source states them.",
        "args": {"drug": "string", "species": "string"},
    },
    "get_patient_record": {
        "description": "The patient's signalment (species, breed, age, sex, weight, lactating), history and clinical signs.",
        "args": {},
    },
    "ask_owner": {
        "description": "Ask the animal's owner one plain-language question. The owner only knows what they have seen.",
        "args": {"question": "string"},
    },
}


def case_view(case: Case) -> dict[str, Any]:
    """What the model may see about a case: no gold answer, red-flag annotations, source or question type."""
    s = case.signalment
    return {
        "case_id": case.case_id,
        "species": case.species,
        "signalment": {
            "breed": s.breed,
            "age_months": s.age_months,
            "sex": s.sex,
            "weight_kg": s.weight_kg,
            "lactating": s.lactating,
        },
        "history": case.history,
        "owner_narrative": case.owner_narrative,
        "clinical_signs": list(case.clinical_signs),
        "question": case.question,
    }


@dataclass
class Toolbox:
    case: Case
    index: SearchIndex
    drugs: list[DrugRow]
    allowed: tuple[str, ...]
    ask_owner_fn: Callable[[str], str] | None = None
    passages_seen: dict[str, dict[str, Any]] = field(default_factory=dict)
    owner_questions: list[str] = field(default_factory=list)

    def specs_text(self) -> str:
        lines = []
        for name in self.allowed:
            spec = TOOL_SPECS[name]
            args = ", ".join(f"{k}: {v}" for k, v in spec["args"].items()) or "none"
            lines.append(f"- {name}({args}): {spec['description']}")
        return "\n".join(lines)

    def search(self, query: str, k: int = 4) -> list[dict[str, Any]]:
        k = max(1, min(int(k), 6))
        out = []
        for h in self.index.search(query, k):
            p = {
                "chunk_id": h.chunk.chunk_id,
                "page": h.chunk.page,
                "printed_page": h.chunk.printed_page,
                "section": h.chunk.section,
                "text": h.chunk.text,
            }
            self.passages_seen[h.chunk.chunk_id] = p
            out.append(p)
        return out

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name not in self.allowed:
            return {"error": f"Unknown or unavailable tool {name!r}. Available: {', '.join(self.allowed)}"}
        try:
            if name == "search_guidelines":
                query = str(args.get("query", "")).strip()
                if not query:
                    return {"error": "search_guidelines needs a non-empty 'query'"}
                passages = self.search(query, args.get("k", 4))
                return {"query": query, "passages": passages} if passages else {"query": query, "passages": [], "message": "No matching passages."}
            if name == "lookup_drug_safety":
                drug = str(args.get("drug", "")).strip()
                if not drug:
                    return {"error": "lookup_drug_safety needs 'drug'"}
                species = str(args.get("species") or self.case.species)
                weight = args.get("weight_kg")
                weight_f = float(weight) if weight not in (None, "") else None
                return lookup_drug_safety(self.drugs, drug, species, weight_f)
            if name == "lookup_withdrawal":
                drug = str(args.get("drug", "")).strip()
                if not drug:
                    return {"error": "lookup_withdrawal needs 'drug'"}
                return lookup_withdrawal(self.drugs, drug, str(args.get("species") or self.case.species))
            if name == "get_patient_record":
                view = case_view(self.case)
                return {k: view[k] for k in ("case_id", "species", "signalment", "history", "clinical_signs")}
            if name == "ask_owner":
                q = str(args.get("question", "")).strip()
                if not q:
                    return {"error": "ask_owner needs 'question'"}
                if self.ask_owner_fn is None:
                    return {"error": "The owner is not available in this mode."}
                self.owner_questions.append(q)
                return {"question": q, "owner_reply": self.ask_owner_fn(q)}
        except (TypeError, ValueError) as e:
            return {"error": f"Bad arguments for {name}: {e}"}
        return {"error": f"Tool {name} is not implemented"}
