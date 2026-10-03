"""Drug-table lookups. Dose arithmetic happens here, never in the model.

Drugs that are not in the table return status "unknown".
"""

import re
from typing import Any

from app.data.models import DrugRow

# Brand names and common alternatives → canonical table name.
ALIASES = {
    "acetaminophen": "paracetamol",
    "crocin": "paracetamol",
    "calpol": "paracetamol",
    "dolo": "paracetamol",
    "grapes": "grapes and raisins",
    "grape": "grapes and raisins",
    "raisins": "grapes and raisins",
    "raisin": "grapes and raisins",
    "kishmish": "grapes and raisins",
    "flunixin": "flunixin meglumine",
    "buparvaquone injection": "buparvaquone",
    "sulfadimidine": "sulphadimidine",
    "sulfadimethoxine": "sulphadimethoxine",
    "sulfamethazine": "sulphamethazine",
}

# A row for a closely related species may stand in when the exact species has none.
RELATED_SPECIES = {"buffalo": "cattle", "cattle": "buffalo", "sheep": "goat", "goat": "sheep"}


def canonical(name: str) -> str:
    n = re.sub(r"\s+", " ", name.strip().lower())
    return ALIASES.get(n, n)


def _find(rows: list[DrugRow], drug: str, species: str) -> tuple[DrugRow | None, str | None]:
    exact = next((r for r in rows if r.drug == drug and r.species == species), None)
    if exact:
        return exact, None
    related = RELATED_SPECIES.get(species)
    if related:
        row = next((r for r in rows if r.drug == drug and r.species == related), None)
        if row:
            return row, related
    return None, None


def lookup_drug_safety(rows: list[DrugRow], drug: str, species: str, weight_kg: float | None = None) -> dict[str, Any]:
    name = canonical(drug)
    species = species.strip().lower()
    banned = next((r for r in rows if r.drug == name and r.status == "banned_in_india"), None)
    row, via = _find(rows, name, species)

    if banned and (row is None or row.status == "banned_in_india"):
        return {
            "drug": name,
            "species": species,
            "status": "banned_in_india",
            "legal_in_india": False,
            "advice": f"Do not give {name}: prohibited for animal use in India (applies to all species).",
            "source": banned.source,
            "notes": banned.notes,
            "verified": banned.verified,
        }
    if row is None:
        return {
            "drug": name,
            "species": species,
            "status": "unknown",
            "message": f"{name} for {species} is not in the drug table; no sourced safety or dose information.",
        }

    out: dict[str, Any] = {
        "drug": name,
        "species": species,
        "status": row.status,
        "legal_in_india": row.legal_in_india,
        "dose_mg_per_kg": None,
        "dose_mg_total": None,
        "source": row.source,
        "notes": row.notes,
        "verified": row.verified,
    }
    if via:
        out["matched_species"] = via
        out["species_note"] = f"No {species} row; using the {via} row."
    if row.status == "contraindicated":
        out["advice"] = f"Do not give {name} to a {species}: contraindicated."
    elif row.dose_min_mg_per_kg is not None and row.dose_max_mg_per_kg is not None:
        out["dose_mg_per_kg"] = {"min": row.dose_min_mg_per_kg, "max": row.dose_max_mg_per_kg}
        if weight_kg is not None and weight_kg > 0:
            out["dose_mg_total"] = {
                "min": round(row.dose_min_mg_per_kg * weight_kg, 2),
                "max": round(row.dose_max_mg_per_kg * weight_kg, 2),
                "weight_kg": weight_kg,
            }
    else:
        out["dose_message"] = "No sourced dose in the drug table."
    return out


def lookup_withdrawal(rows: list[DrugRow], drug: str, species: str) -> dict[str, Any]:
    name = canonical(drug)
    species = species.strip().lower()
    row, via = _find(rows, name, species)
    if row is None:
        return {
            "drug": name,
            "species": species,
            "known": False,
            "status": "unknown",
            "message": f"{name} for {species} is not in the drug table; no sourced withdrawal period.",
        }
    known = row.milk_withdrawal_days is not None or row.meat_withdrawal_days is not None
    out: dict[str, Any] = {
        "drug": name,
        "species": species,
        "known": known,
        "milk_withdrawal_days": row.milk_withdrawal_days,
        "meat_withdrawal_days": row.meat_withdrawal_days,
        "source": row.source,
        "verified": row.verified,
    }
    if via:
        out["matched_species"] = via
    if not known:
        out["message"] = "No withdrawal period is stated in the sourced table. Check the product label; do not guess."
    return out


def detect_drugs(rows: list[DrugRow], text: str) -> list[str]:
    """Canonical drug names mentioned in free text, in order of first appearance."""
    low = text.lower()
    names = {r.drug for r in rows} | set(ALIASES)
    found: list[tuple[int, str]] = []
    for n in names:
        m = re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", low)
        if m:
            found.append((m.start(), canonical(n)))
    seen: list[str] = []
    for _, name in sorted(found):
        if name not in seen:
            seen.append(name)
    return seen
