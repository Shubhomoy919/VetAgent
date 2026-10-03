"""C4 deterministic guardrails, applied after the model's (C3) answer.

Rules (each firing is logged with the fields it changed):
  banned_drug          drug in the question/advice is banned in India → "do not give", status banned, no dose
  contraindicated_drug drug is contraindicated for the species → "do not give", status contraindicated, no dose
  unsourced_withdrawal withdrawal days not backed by the drug table → replaced by the sourced value or cleared
  red_flag             red-flag pattern in the case text → escalate, see vet, triage raised
  notifiable           most likely diagnosis is notifiable (SVTG) → escalate and report
  zoonotic             most likely diagnosis is zoonotic → zoonosis warning
"""

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.agent.schema import FinalAnswer
from app.config import DATA_DIR
from app.data.models import Case, DrugRow
from app.tools.drugs import RELATED_SPECIES, detect_drugs

SEED_PATH = DATA_DIR / "knowledge_seed.json"
TRIAGE_ORDER = {"routine": 0, "urgent": 1, "emergency": 2}


class SeedDisease(BaseModel):
    name: str
    synonyms: list[str] = []
    notifiable: bool | None = None
    notifiable_source: str = ""
    zoonotic: bool = False
    zoonotic_source: str = ""


class SeedRedFlag(BaseModel):
    id: str
    label: str
    pattern: str
    min_triage: Literal["urgent", "emergency"]


class Seed(BaseModel):
    version: int
    diseases: list[SeedDisease]
    red_flags: list[SeedRedFlag]


@lru_cache(maxsize=2)
def _load_seed(path: str, mtime: float) -> Seed:
    return Seed.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def load_seed(path: Path = SEED_PATH) -> Seed:
    return _load_seed(str(path), path.stat().st_mtime)


@dataclass
class RuleFiring:
    rule: str
    detail: str
    changes: dict[str, list[Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def case_text(case: Case) -> str:
    return " ".join([case.history, case.owner_narrative, " ".join(case.clinical_signs), case.question])


def match_disease(seed: Seed, text: str) -> SeedDisease | None:
    low = text.lower()
    for d in seed.diseases:
        for name in [d.name, *d.synonyms]:
            n = name.lower()
            if len(n) <= 4:
                if re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low):
                    return d
            elif n in low:
                return d
    return None


def red_flags_in(seed: Seed, text: str) -> list[SeedRedFlag]:
    low = text.lower()
    return [rf for rf in seed.red_flags if re.search(rf.pattern, low)]


def _prefix(advice: str, note: str) -> str:
    return advice if note.lower() in advice.lower() else f"{note} {advice}"


def _append(advice: str, note: str) -> str:
    return advice if note.lower() in advice.lower() else f"{advice} {note}"


def apply_guardrails(
    answer: FinalAnswer, case: Case, drugs: list[DrugRow], seed: Seed | None = None
) -> tuple[FinalAnswer, list[RuleFiring]]:
    seed = seed or load_seed()
    a = answer.model_copy(deep=True)
    fired: list[RuleFiring] = []
    text = case_text(case)
    asked = detect_drugs(drugs, text)
    recommended = [d for d in detect_drugs(drugs, a.advice) if d not in asked]
    species = case.species
    related = RELATED_SPECIES.get(species)

    def change(f: RuleFiring, name: str, new: Any) -> None:
        old = getattr(a, name)
        if old != new:
            f.changes[name] = [old, new]
            setattr(a, name, new)

    # 1. Banned drugs (ban applies to every species).
    banned = {r.drug for r in drugs if r.status == "banned_in_india"}
    for d in [*asked, *recommended]:
        if d not in banned:
            continue
        f = RuleFiring("banned_drug", f"{d} is prohibited for animal use in India")
        if asked and d == asked[0]:  # the drug the owner asks about
            change(f, "drug_status", "banned_in_india")
            change(f, "dose_mg", None)
        change(f, "advice", _prefix(a.advice, f"DO NOT GIVE {d.upper()}: banned for animal use in India."))
        if f.changes:
            fired.append(f)

    # 2. Contraindicated for this species.
    contra = {r.drug for r in drugs if r.status == "contraindicated" and r.species in (species, related)}
    for d in asked:
        if d not in contra:
            continue
        f = RuleFiring("contraindicated_drug", f"{d} is contraindicated in {species}")
        if d == asked[0]:
            change(f, "drug_status", "contraindicated")
            change(f, "dose_mg", None)
        change(f, "see_vet", True)
        change(f, "advice", _prefix(a.advice, f"DO NOT GIVE {d.upper()} to this {species}: it is toxic/contraindicated."))
        if f.changes:
            fired.append(f)

    # 3. Withdrawal days must come from the drug table.
    if a.withdrawal_days is not None:
        row = None
        if asked:
            row = next((r for r in drugs if r.drug == asked[0] and r.species == species), None) or next(
                (r for r in drugs if r.drug == asked[0] and r.species == related), None
            )
        sourced = None
        if row is not None:
            milk_context = case.signalment.lactating or "milk" in text.lower()
            sourced = row.milk_withdrawal_days if milk_context else row.meat_withdrawal_days
            if sourced is None:
                sourced = row.meat_withdrawal_days if milk_context else row.milk_withdrawal_days
        if sourced != a.withdrawal_days:
            if sourced is None:
                f = RuleFiring("unsourced_withdrawal", "no sourced withdrawal period; model value cleared")
                change(f, "withdrawal_days", None)
                change(
                    f,
                    "advice",
                    _append(a.advice, "No sourced withdrawal period is available: check the product label and do not sell milk or meat until it has passed."),
                )
            else:
                f = RuleFiring("unsourced_withdrawal", f"withdrawal replaced with sourced value ({sourced:g} days)")
                change(f, "withdrawal_days", sourced)
            fired.append(f)

    # 4. Red flags → escalate.
    flags = red_flags_in(seed, text)
    if flags:
        worst = max(flags, key=lambda rf: TRIAGE_ORDER[rf.min_triage])
        f = RuleFiring("red_flag", "; ".join(rf.label for rf in flags))
        change(f, "escalate", True)
        change(f, "see_vet", True)
        if TRIAGE_ORDER[a.triage] < TRIAGE_ORDER[worst.min_triage]:
            change(f, "triage", worst.min_triage)
        if f.changes:
            fired.append(f)

    # 5/6. Notifiable and zoonotic diagnoses.
    disease = match_disease(seed, a.most_likely)
    if disease and disease.notifiable:
        f = RuleFiring("notifiable", f"{disease.name} is notifiable ({disease.notifiable_source})")
        change(f, "escalate", True)
        change(f, "see_vet", True)
        change(f, "advice", _append(a.advice, f"Report suspected {disease.name} to the local veterinary authority."))
        if f.changes:
            fired.append(f)
    if disease and disease.zoonotic:
        f = RuleFiring("zoonotic", f"{disease.name} can infect people ({disease.zoonotic_source})")
        change(f, "zoonosis_warning", True)
        change(
            f,
            "advice",
            _append(a.advice, f"{disease.name.capitalize()} can spread to people: avoid bare-hand contact and protect your family."),
        )
        if f.changes:
            fired.append(f)

    return a, fired
