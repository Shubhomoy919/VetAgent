"""Case and drug-table schemas with the project's validation rules.

Every case and drug row starts unverified. Clinical numbers (doses, withdrawal
days) are only filled in when a source states them; otherwise they stay blank.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

Species = Literal["dog", "cat", "cattle", "buffalo", "goat", "sheep", "poultry"]
QuestionType = Literal["diagnosis", "triage", "drug_safety", "withdrawal_legal", "escalation"]
Triage = Literal["emergency", "urgent", "routine"]
DrugStatus = Literal["safe", "contraindicated", "banned_in_india"]
AnswerDrugStatus = Literal["safe", "contraindicated", "banned_in_india", "n/a"]
Sex = Literal["male", "female", "male_castrated", "female_spayed"]

QUESTION_TYPES: tuple[QuestionType, ...] = (
    "diagnosis",
    "triage",
    "drug_safety",
    "withdrawal_legal",
    "escalation",
)

# Case-ID species codes.
PREFIX_SPECIES: dict[str, tuple[Species, ...]] = {
    "CAN": ("dog",),
    "FEL": ("cat",),
    "BOV": ("cattle", "buffalo"),
    "CAP": ("goat", "sheep"),
    "AVI": ("poultry",),
}
SPECIES_PREFIX: dict[str, str] = {s: p for p, group in PREFIX_SPECIES.items() for s in group}

CASE_ID_RE = re.compile(r"^(CAN|FEL|BOV|CAP|AVI)-(?:[A-Z]+-)?\d{3}$")

# Plausible body-weight ranges (kg). Dogs: small 3–15 or large 20–45.
WEIGHT_RANGES: dict[str, tuple[tuple[float, float], ...]] = {
    "cat": ((2, 7),),
    "dog": ((3, 15), (20, 45)),
    "goat": ((20, 70),),
    "sheep": ((20, 70),),
    "cattle": ((250, 600),),
    "buffalo": ((250, 600),),
    "poultry": ((1, 3),),
}


def weight_in_range(species: str, weight_kg: float) -> bool:
    return any(lo <= weight_kg <= hi for lo, hi in WEIGHT_RANGES[species])


def describe_range(species: str) -> str:
    return " or ".join(f"{lo:g}–{hi:g} kg" for lo, hi in WEIGHT_RANGES[species])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Citation(Strict):
    source: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1, description="PDF page number (1-based)")


class Signalment(Strict):
    breed: str = Field(min_length=1)
    age_months: float = Field(gt=0, le=300)
    sex: Sex
    weight_kg: float = Field(gt=0)
    lactating: bool = False

    @model_validator(mode="after")
    def _lactating_needs_female(self) -> "Signalment":
        if self.lactating and self.sex != "female":
            raise ValueError(f"lactating=true is only valid for an entire female, not sex={self.sex!r}")
        return self


class DoseRange(Strict):
    min: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> "DoseRange":
        if self.min > self.max:
            raise ValueError(f"dose min {self.min} is greater than max {self.max}")
        return self


class GoldAnswer(Strict):
    most_likely: str = Field(min_length=1)
    acceptable_diagnoses: list[str] = Field(min_length=1, description="Synonyms counted as correct")
    differentials: list[str] = Field(default_factory=list)
    triage: Triage
    drug: str | None = None
    drug_status: AnswerDrugStatus = "n/a"
    dose_mg: DoseRange | None = None
    withdrawal_known: bool | None = Field(
        default=None, description="True if a source states the withdrawal period; False if no source does"
    )
    withdrawal_days: float | None = Field(default=None, ge=0)
    escalate: bool
    zoonosis_warning: bool
    notifiable: bool | None = Field(default=None, description="None = not stated in the source")
    key_points: list[str] = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "GoldAnswer":
        if self.drug is None and self.drug_status != "n/a":
            raise ValueError("drug_status must be 'n/a' when no drug is named")
        if self.drug is not None and self.drug_status == "n/a":
            raise ValueError(f"drug {self.drug!r} needs a drug_status")
        if self.withdrawal_known is True and self.withdrawal_days is None:
            raise ValueError("withdrawal_known=true requires withdrawal_days")
        if self.withdrawal_known is not True and self.withdrawal_days is not None:
            raise ValueError("withdrawal_days given but withdrawal_known is not true")
        if self.dose_mg is not None and self.drug_status in ("contraindicated", "banned_in_india"):
            raise ValueError("a contraindicated or banned drug must not have a gold dose")
        if self.most_likely not in self.acceptable_diagnoses:
            raise ValueError("most_likely must also appear in acceptable_diagnoses")
        return self


class Case(Strict):
    case_id: str
    species: Species
    signalment: Signalment
    history: str = Field(min_length=1)
    owner_narrative: str = Field(min_length=1)
    clinical_signs: list[str] = Field(min_length=1)
    question_type: QuestionType
    question: str = Field(min_length=1)
    gold_answer: GoldAnswer
    red_flags: list[str] = Field(default_factory=list)
    source: str = Field(min_length=1)
    vet_verified: bool = False

    @field_validator("case_id")
    @classmethod
    def _id_format(cls, v: str) -> str:
        if not CASE_ID_RE.match(v):
            raise ValueError(
                f"case_id {v!r} must look like BOV-007 or BOV-WD-007 with prefix CAN/FEL/BOV/CAP/AVI"
            )
        return v

    @model_validator(mode="after")
    def _species_rules(self) -> "Case":
        prefix = self.case_id.split("-", 1)[0]
        if self.species not in PREFIX_SPECIES[prefix]:
            raise ValueError(
                f"{self.case_id}: prefix {prefix} is for {'/'.join(PREFIX_SPECIES[prefix])}, "
                f"but species is {self.species!r}"
            )
        w = self.signalment.weight_kg
        if not weight_in_range(self.species, w):
            raise ValueError(
                f"{self.case_id}: weight {w:g} kg is outside the {self.species} range ({describe_range(self.species)})"
            )
        g = self.gold_answer
        if self.question_type == "drug_safety" and g.drug is None:
            raise ValueError(f"{self.case_id}: drug_safety cases must name a drug in gold_answer")
        if self.question_type == "withdrawal_legal" and g.withdrawal_known is None:
            raise ValueError(f"{self.case_id}: withdrawal_legal cases must set gold_answer.withdrawal_known")
        return self


def _blank_to_none(v: object) -> object:
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class DrugRow(Strict):
    species: Species
    drug: str = Field(min_length=1)
    status: DrugStatus
    dose_min_mg_per_kg: float | None = Field(default=None, ge=0)
    dose_max_mg_per_kg: float | None = Field(default=None, ge=0)
    milk_withdrawal_days: float | None = Field(default=None, ge=0)
    meat_withdrawal_days: float | None = Field(default=None, ge=0)
    legal_in_india: bool
    source: str = Field(min_length=1)
    notes: str = ""
    verified_by: str = ""
    verified_on: str = ""

    @field_validator(
        "dose_min_mg_per_kg",
        "dose_max_mg_per_kg",
        "milk_withdrawal_days",
        "meat_withdrawal_days",
        mode="before",
    )
    @classmethod
    def _blank_numbers(cls, v: object) -> object:
        return _blank_to_none(v)

    @field_validator("legal_in_india", mode="before")
    @classmethod
    def _parse_bool(cls, v: object) -> object:
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "yes", "1"):
                return True
            if s in ("false", "no", "0"):
                return False
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def verified(self) -> bool:
        return bool(self.verified_by and self.verified_on)

    @model_validator(mode="after")
    def _rules(self) -> "DrugRow":
        lo, hi = self.dose_min_mg_per_kg, self.dose_max_mg_per_kg
        if (lo is None) != (hi is None):
            raise ValueError(f"{self.species}/{self.drug}: give both dose_min and dose_max, or neither")
        if lo is not None and hi is not None and lo > hi:
            raise ValueError(f"{self.species}/{self.drug}: dose_min {lo} > dose_max {hi}")
        if self.status == "banned_in_india":
            if self.legal_in_india:
                raise ValueError(f"{self.species}/{self.drug}: banned_in_india rows must have legal_in_india=false")
            if lo is not None:
                raise ValueError(f"{self.species}/{self.drug}: banned drugs must not carry a dose")
        if self.status == "contraindicated" and lo is not None:
            raise ValueError(f"{self.species}/{self.drug}: contraindicated drugs must not carry a dose")
        if bool(self.verified_by) != bool(self.verified_on):
            raise ValueError(f"{self.species}/{self.drug}: verified_by and verified_on go together")
        return self
