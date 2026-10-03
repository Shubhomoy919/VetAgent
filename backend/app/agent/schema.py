"""The final-answer schema shared by every condition."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Triage = Literal["emergency", "urgent", "routine"]
AnswerDrugStatus = Literal["safe", "contraindicated", "banned_in_india", "n/a"]


class AnswerCitation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)


class FinalAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    differentials: list[str] = Field(default_factory=list)
    most_likely: str = Field(min_length=1)
    triage: Triage
    drug_status: AnswerDrugStatus = "n/a"
    dose_mg: float | None = Field(default=None, ge=0)
    withdrawal_days: float | None = Field(default=None, ge=0)
    escalate: bool
    zoonosis_warning: bool
    see_vet: bool
    advice: str = Field(min_length=1)
    citations: list[AnswerCitation] = Field(default_factory=list)

    @field_validator("triage", "drug_status", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.strip().lower().replace(" ", "_") if isinstance(v, str) else v

    @field_validator("drug_status", mode="before")
    @classmethod
    def _na(cls, v: object) -> object:
        if v is None or (isinstance(v, str) and v.strip().lower() in ("", "na", "n/a", "none", "not_applicable")):
            return "n/a"
        return v

    @field_validator("dose_mg", "withdrawal_days", mode="before")
    @classmethod
    def _blank_number(cls, v: object) -> object:
        if isinstance(v, str) and v.strip().lower() in ("", "null", "none", "unknown", "n/a"):
            return None
        return v


FINAL_ANSWER_SPEC = """{
  "differentials": [string, ...],          // ranked, most likely first
  "most_likely": string,                   // single most likely diagnosis
  "triage": "emergency" | "urgent" | "routine",
  "drug_status": "safe" | "contraindicated" | "banned_in_india" | "n/a",  // for the drug the owner asks about; "n/a" if none
  "dose_mg": number | null,                // total dose in mg for this animal, only if sourced; else null
  "withdrawal_days": number | null,        // milk/meat withdrawal in days, only if sourced; else null
  "escalate": boolean,                     // needs a veterinarian urgently or must be reported to authorities
  "zoonosis_warning": boolean,             // people are at risk
  "see_vet": boolean,
  "advice": string,                        // plain-language advice to the owner
  "citations": [{"source": "SVTG", "page": number}]   // SVTG PDF pages you relied on; [] if none
}"""
