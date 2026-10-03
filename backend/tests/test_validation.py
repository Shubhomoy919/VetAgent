import copy

import pytest
from pydantic import ValidationError

from app.data.models import Case, DrugRow, weight_in_range

BASE_CASE = {
    "case_id": "BOV-900",
    "species": "cattle",
    "signalment": {"breed": "Gir", "age_months": 48, "sex": "female", "weight_kg": 400, "lactating": True},
    "history": "h",
    "owner_narrative": "n",
    "clinical_signs": ["s"],
    "question_type": "diagnosis",
    "question": "q",
    "gold_answer": {
        "most_likely": "milk fever",
        "acceptable_diagnoses": ["milk fever"],
        "triage": "emergency",
        "escalate": True,
        "zoonosis_warning": False,
        "key_points": ["k"],
    },
    "red_flags": [],
    "source": "test",
}


def case(**changes) -> dict:
    c = copy.deepcopy(BASE_CASE)
    for path, value in changes.items():
        target = c
        keys = path.split("__")
        for k in keys[:-1]:
            target = target[k]
        target[keys[-1]] = value
    return c


def test_base_case_is_valid():
    Case.model_validate(case())


# ---------- weight ranges ----------

@pytest.mark.parametrize(
    "species,weight,ok",
    [
        ("cat", 2, True), ("cat", 7, True), ("cat", 1.5, False), ("cat", 8, False),
        ("dog", 3, True), ("dog", 15, True), ("dog", 20, True), ("dog", 45, True),
        ("dog", 17, False), ("dog", 2, False), ("dog", 50, False),
        ("goat", 20, True), ("goat", 70, True), ("goat", 12, False),
        ("sheep", 45, True), ("sheep", 80, False),
        ("cattle", 250, True), ("cattle", 600, True), ("cattle", 200, False), ("cattle", 700, False),
        ("buffalo", 520, True), ("buffalo", 650, False),
        ("poultry", 1, True), ("poultry", 3, True), ("poultry", 0.5, False), ("poultry", 4, False),
    ],
)
def test_weight_ranges(species, weight, ok):
    assert weight_in_range(species, weight) is ok


def test_case_rejects_out_of_range_weight():
    with pytest.raises(ValidationError, match="outside the cattle range"):
        Case.model_validate(case(signalment__weight_kg=120))


def test_cat_weight_enforced():
    with pytest.raises(ValidationError, match="cat range"):
        Case.model_validate(
            case(case_id="FEL-900", species="cat", signalment__weight_kg=9, signalment__lactating=False)
        )


# ---------- IDs and species codes ----------

@pytest.mark.parametrize("cid", ["BOV-007", "BOV-WD-007", "FEL-SAFE-004", "CAN-013", "AVI-001", "CAP-WD-006"])
def test_valid_ids(cid):
    prefix = cid.split("-")[0]
    species = {"BOV": "cattle", "FEL": "cat", "CAN": "dog", "AVI": "poultry", "CAP": "goat"}[prefix]
    weight = {"cattle": 400, "cat": 4, "dog": 10, "poultry": 2, "goat": 30}[species]
    Case.model_validate(
        case(case_id=cid, species=species, signalment__weight_kg=weight, signalment__lactating=False)
    )


@pytest.mark.parametrize("cid", ["BOV7", "bov-007", "EQU-001", "BOV-07", "BOV-wd-007", "BOV-007-X"])
def test_invalid_ids(cid):
    with pytest.raises(ValidationError, match="case_id"):
        Case.model_validate(case(case_id=cid))


def test_prefix_must_match_species():
    with pytest.raises(ValidationError, match="prefix CAP is for goat/sheep"):
        Case.model_validate(case(case_id="CAP-900"))


def test_buffalo_allowed_under_bov():
    Case.model_validate(case(species="buffalo"))


# ---------- signalment and enums ----------

def test_lactating_male_rejected():
    with pytest.raises(ValidationError, match="lactating"):
        Case.model_validate(case(signalment__sex="male"))


def test_unknown_question_type_rejected():
    with pytest.raises(ValidationError):
        Case.model_validate(case(question_type="prognosis"))


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        Case.model_validate(case(unexpected="x"))


def test_vet_verified_defaults_false():
    data = case()
    data.pop("vet_verified", None)
    assert Case.model_validate(data).vet_verified is False


# ---------- gold answer consistency ----------

def test_drug_safety_case_needs_drug():
    with pytest.raises(ValidationError, match="must name a drug"):
        Case.model_validate(case(question_type="drug_safety"))


def test_withdrawal_case_needs_withdrawal_known():
    with pytest.raises(ValidationError, match="withdrawal_known"):
        Case.model_validate(case(question_type="withdrawal_legal"))


def test_withdrawal_days_without_known_rejected():
    with pytest.raises(ValidationError, match="withdrawal_known"):
        Case.model_validate(case(gold_answer__withdrawal_days=3))


def test_banned_drug_cannot_have_gold_dose():
    with pytest.raises(ValidationError, match="must not have a gold dose"):
        Case.model_validate(
            case(
                gold_answer__drug="diclofenac",
                gold_answer__drug_status="banned_in_india",
                gold_answer__dose_mg={"min": 1, "max": 2},
            )
        )


def test_most_likely_must_be_acceptable():
    with pytest.raises(ValidationError, match="acceptable_diagnoses"):
        Case.model_validate(case(gold_answer__acceptable_diagnoses=["ketosis"]))


# ---------- drug rows ----------

BASE_DRUG = {
    "species": "cattle",
    "drug": "meloxicam",
    "status": "safe",
    "dose_min_mg_per_kg": "0.5",
    "dose_max_mg_per_kg": "0.5",
    "milk_withdrawal_days": "",
    "meat_withdrawal_days": "",
    "legal_in_india": "true",
    "source": "SVTG",
    "notes": "",
    "verified_by": "",
    "verified_on": "",
}


def drug(**changes) -> dict:
    return {**BASE_DRUG, **changes}


def test_csv_style_drug_row_parses_blanks_and_bools():
    row = DrugRow.model_validate(drug())
    assert row.milk_withdrawal_days is None
    assert row.legal_in_india is True
    assert row.verified is False


def test_banned_drug_must_be_illegal():
    with pytest.raises(ValidationError, match="legal_in_india=false"):
        DrugRow.model_validate(drug(drug="diclofenac", status="banned_in_india", dose_min_mg_per_kg="", dose_max_mg_per_kg=""))


def test_banned_drug_cannot_carry_dose():
    with pytest.raises(ValidationError, match="must not carry a dose"):
        DrugRow.model_validate(drug(drug="ketoprofen", status="banned_in_india", legal_in_india="false"))


def test_contraindicated_cannot_carry_dose():
    with pytest.raises(ValidationError, match="must not carry a dose"):
        DrugRow.model_validate(drug(species="cat", drug="paracetamol", status="contraindicated"))


def test_dose_min_le_max():
    with pytest.raises(ValidationError, match="dose_min"):
        DrugRow.model_validate(drug(dose_min_mg_per_kg="5", dose_max_mg_per_kg="1"))


def test_dose_needs_both_bounds():
    with pytest.raises(ValidationError, match="both dose_min and dose_max"):
        DrugRow.model_validate(drug(dose_max_mg_per_kg=""))


def test_unknown_status_rejected():
    with pytest.raises(ValidationError):
        DrugRow.model_validate(drug(status="maybe"))


def test_verified_needs_both_fields():
    with pytest.raises(ValidationError, match="go together"):
        DrugRow.model_validate(drug(verified_by="Dr X"))
