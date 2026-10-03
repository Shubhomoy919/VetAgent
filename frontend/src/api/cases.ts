import { useQuery } from "@tanstack/react-query";

/** Mirrors backend/app/data/models.py */
export type Species = "dog" | "cat" | "cattle" | "buffalo" | "goat" | "sheep" | "poultry";
export type QuestionType = "diagnosis" | "triage" | "drug_safety" | "withdrawal_legal" | "escalation";
export type Triage = "emergency" | "urgent" | "routine";
export type DrugStatus = "safe" | "contraindicated" | "banned_in_india";
export type SpeciesCode = "CAN" | "FEL" | "BOV" | "CAP" | "AVI";

export interface Citation {
  source: string;
  page: number | null;
}

export interface GoldAnswer {
  most_likely: string;
  acceptable_diagnoses: string[];
  differentials: string[];
  triage: Triage;
  drug: string | null;
  drug_status: DrugStatus | "n/a";
  dose_mg: { min: number; max: number } | null;
  withdrawal_known: boolean | null;
  withdrawal_days: number | null;
  escalate: boolean;
  zoonosis_warning: boolean;
  notifiable: boolean | null;
  key_points: string[];
  citations: Citation[];
}

export interface Case {
  case_id: string;
  species: Species;
  signalment: {
    breed: string;
    age_months: number;
    sex: "male" | "female" | "male_castrated" | "female_spayed";
    weight_kg: number;
    lactating: boolean;
  };
  history: string;
  owner_narrative: string;
  clinical_signs: string[];
  question_type: QuestionType;
  question: string;
  gold_answer: GoldAnswer;
  red_flags: string[];
  source: string;
  vet_verified: boolean;
}

export const QUESTION_TYPE_LABEL: Record<QuestionType, string> = {
  diagnosis: "Diagnosis",
  triage: "Triage",
  drug_safety: "Drug safety",
  withdrawal_legal: "Withdrawal",
  escalation: "Escalation",
};

export const SPECIES_CODES: SpeciesCode[] = ["BOV", "CAP", "AVI", "CAN", "FEL"];

export const SPECIES_CODE_LABEL: Record<SpeciesCode, string> = {
  BOV: "Cattle / buffalo",
  CAP: "Goat / sheep",
  AVI: "Poultry",
  CAN: "Dog",
  FEL: "Cat",
};

export function speciesCode(caseId: string): SpeciesCode {
  return caseId.split("-")[0] as SpeciesCode;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON error body
    }
    throw new Error(`GET ${url} → ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export function useCases() {
  return useQuery({ queryKey: ["cases"], queryFn: () => getJson<Case[]>("/api/cases") });
}

export function formatAge(months: number): string {
  if (months < 2) return `${Math.round(months * 30.4)} d`;
  if (months < 24) return `${Number(months.toFixed(1))} mo`;
  return `${Number((months / 12).toFixed(1))} y`;
}

export function formatSex(sex: Case["signalment"]["sex"]): string {
  return { male: "Male", female: "Female", male_castrated: "Male (castrated)", female_spayed: "Female (spayed)" }[sex];
}
