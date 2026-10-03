import type { Case } from "../../api/cases";
import type { ValidationMeta } from "../../api/data";

/** Flat, string-based form state for editing one case. Lists are one item per line. */
export interface CaseForm {
  case_id: string;
  species: string;
  breed: string;
  age_months: string;
  sex: string;
  weight_kg: string;
  lactating: boolean;
  history: string;
  owner_narrative: string;
  clinical_signs: string;
  question_type: string;
  question: string;
  red_flags: string;
  source: string;
  vet_verified: boolean;
  g_most_likely: string;
  g_acceptable: string;
  g_differentials: string;
  g_triage: string;
  g_drug: string;
  g_drug_status: string;
  g_dose_min: string;
  g_dose_max: string;
  g_withdrawal_known: "null" | "true" | "false";
  g_withdrawal_days: string;
  g_escalate: boolean;
  g_zoonosis: boolean;
  g_notifiable: "null" | "true" | "false";
  g_key_points: string;
  g_citations: string;
}

const lines = (xs: string[]) => xs.join("\n");
const toLines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
const tri = (v: boolean | null): "null" | "true" | "false" => (v === null ? "null" : v ? "true" : "false");
const fromTri = (v: string): boolean | null => (v === "null" ? null : v === "true");
const str = (n: number | null | undefined) => (n === null || n === undefined ? "" : String(n));

/** Number fields: "" → null, numeric → number, anything else is sent as typed so the server explains the error. */
function num(s: string): number | string | null {
  const t = s.trim();
  if (t === "") return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : t;
}

export function emptyForm(): CaseForm {
  return {
    case_id: "", species: "cattle", breed: "", age_months: "", sex: "female", weight_kg: "", lactating: false,
    history: "", owner_narrative: "", clinical_signs: "", question_type: "diagnosis", question: "", red_flags: "",
    source: "", vet_verified: false, g_most_likely: "", g_acceptable: "", g_differentials: "", g_triage: "urgent",
    g_drug: "", g_drug_status: "n/a", g_dose_min: "", g_dose_max: "", g_withdrawal_known: "null",
    g_withdrawal_days: "", g_escalate: false, g_zoonosis: false, g_notifiable: "null", g_key_points: "",
    g_citations: "",
  };
}

export function fromCase(c: Case): CaseForm {
  const g = c.gold_answer;
  return {
    case_id: c.case_id,
    species: c.species,
    breed: c.signalment.breed,
    age_months: str(c.signalment.age_months),
    sex: c.signalment.sex,
    weight_kg: str(c.signalment.weight_kg),
    lactating: c.signalment.lactating,
    history: c.history,
    owner_narrative: c.owner_narrative,
    clinical_signs: lines(c.clinical_signs),
    question_type: c.question_type,
    question: c.question,
    red_flags: lines(c.red_flags),
    source: c.source,
    vet_verified: c.vet_verified,
    g_most_likely: g.most_likely,
    g_acceptable: lines(g.acceptable_diagnoses),
    g_differentials: lines(g.differentials),
    g_triage: g.triage,
    g_drug: g.drug ?? "",
    g_drug_status: g.drug_status,
    g_dose_min: str(g.dose_mg?.min),
    g_dose_max: str(g.dose_mg?.max),
    g_withdrawal_known: tri(g.withdrawal_known),
    g_withdrawal_days: str(g.withdrawal_days),
    g_escalate: g.escalate,
    g_zoonosis: g.zoonosis_warning,
    g_notifiable: tri(g.notifiable),
    g_key_points: lines(g.key_points),
    g_citations: g.citations.map((ci) => (ci.page ? `${ci.source} | ${ci.page}` : ci.source)).join("\n"),
  };
}

export function toPayload(f: CaseForm): Record<string, unknown> {
  const doseMin = num(f.g_dose_min);
  const doseMax = num(f.g_dose_max);
  return {
    case_id: f.case_id.trim(),
    species: f.species,
    signalment: {
      breed: f.breed,
      age_months: num(f.age_months),
      sex: f.sex,
      weight_kg: num(f.weight_kg),
      lactating: f.lactating,
    },
    history: f.history,
    owner_narrative: f.owner_narrative,
    clinical_signs: toLines(f.clinical_signs),
    question_type: f.question_type,
    question: f.question,
    red_flags: toLines(f.red_flags),
    source: f.source,
    vet_verified: f.vet_verified,
    gold_answer: {
      most_likely: f.g_most_likely,
      acceptable_diagnoses: toLines(f.g_acceptable),
      differentials: toLines(f.g_differentials),
      triage: f.g_triage,
      drug: f.g_drug.trim() || null,
      drug_status: f.g_drug_status,
      dose_mg: doseMin === null && doseMax === null ? null : { min: doseMin, max: doseMax },
      withdrawal_known: fromTri(f.g_withdrawal_known),
      withdrawal_days: num(f.g_withdrawal_days),
      escalate: f.g_escalate,
      zoonosis_warning: f.g_zoonosis,
      notifiable: fromTri(f.g_notifiable),
      key_points: toLines(f.g_key_points),
      citations: toLines(f.g_citations).map((l) => {
        const [source, page] = l.split("|").map((x) => x.trim());
        const p = page ? Number(page) : null;
        return { source: source ?? "", page: p !== null && Number.isFinite(p) ? p : page ? page : null };
      }),
    },
  };
}

/** Server error location ("signalment.weight_kg") → form field name. */
export function locToField(loc: string): keyof CaseForm | null {
  const map: Record<string, keyof CaseForm> = {
    case_id: "case_id",
    species: "species",
    "signalment.breed": "breed",
    "signalment.age_months": "age_months",
    "signalment.sex": "sex",
    "signalment.weight_kg": "weight_kg",
    "signalment.lactating": "lactating",
    history: "history",
    owner_narrative: "owner_narrative",
    clinical_signs: "clinical_signs",
    question_type: "question_type",
    question: "question",
    red_flags: "red_flags",
    source: "source",
    "gold_answer.most_likely": "g_most_likely",
    "gold_answer.acceptable_diagnoses": "g_acceptable",
    "gold_answer.triage": "g_triage",
    "gold_answer.drug": "g_drug",
    "gold_answer.drug_status": "g_drug_status",
    "gold_answer.dose_mg.min": "g_dose_min",
    "gold_answer.dose_mg.max": "g_dose_max",
    "gold_answer.dose_mg": "g_dose_min",
    "gold_answer.withdrawal_days": "g_withdrawal_days",
    "gold_answer.withdrawal_known": "g_withdrawal_known",
    "gold_answer.key_points": "g_key_points",
  };
  if (map[loc]) return map[loc];
  if (loc.startsWith("gold_answer.citations")) return "g_citations";
  if (loc.startsWith("clinical_signs")) return "clinical_signs";
  return null;
}

/** Instant checks that mirror the server rules (the server stays the source of truth). */
export function clientErrors(f: CaseForm, meta: ValidationMeta | undefined): Partial<Record<keyof CaseForm, string>> {
  const e: Partial<Record<keyof CaseForm, string>> = {};
  const id = f.case_id.trim();
  if (meta) {
    if (!new RegExp(meta.case_id_pattern).test(id)) {
      e.case_id = "Use a species-coded ID such as BOV-007 or BOV-WD-007 (CAN, FEL, BOV, CAP, AVI)";
    } else {
      const prefix = id.split("-")[0] ?? "";
      const allowed = meta.prefix_species[prefix] ?? [];
      if (!allowed.includes(f.species as never)) e.species = `${prefix} is for ${allowed.join(" / ")}`;
    }
    const w = Number(f.weight_kg);
    const ranges = meta.weight_ranges[f.species as keyof typeof meta.weight_ranges];
    if (f.weight_kg.trim() === "" || !Number.isFinite(w)) e.weight_kg = "Enter a weight in kg";
    else if (ranges && !ranges.some(([lo, hi]) => w >= lo && w <= hi)) {
      e.weight_kg = `Outside the ${f.species} range (${ranges.map(([lo, hi]) => `${lo}–${hi} kg`).join(" or ")})`;
    }
  }
  const age = Number(f.age_months);
  if (f.age_months.trim() === "" || !Number.isFinite(age) || age <= 0) e.age_months = "Age must be more than 0 months";
  if (f.lactating && f.sex !== "female") e.lactating = "Only an entire female can be lactating";
  for (const k of ["breed", "history", "owner_narrative", "question", "source", "g_most_likely"] as const) {
    if (!f[k].trim()) e[k] = "Required";
  }
  if (!toLines(f.clinical_signs).length) e.clinical_signs = "Add at least one sign";
  if (!toLines(f.g_key_points).length) e.g_key_points = "Add at least one key point";
  const acc = toLines(f.g_acceptable);
  if (f.g_most_likely.trim() && !acc.includes(f.g_most_likely.trim())) e.g_acceptable = "Must include the most likely diagnosis";
  if (f.question_type === "drug_safety" && !f.g_drug.trim()) e.g_drug = "Drug-safety cases must name a drug";
  if (f.g_drug.trim() && f.g_drug_status === "n/a") e.g_drug_status = "Choose the drug's status";
  if (f.question_type === "withdrawal_legal" && f.g_withdrawal_known === "null") e.g_withdrawal_known = "Say whether a source states it";
  if (f.g_withdrawal_known === "true" && f.g_withdrawal_days.trim() === "") e.g_withdrawal_days = "Give the sourced number of days";
  if (f.g_withdrawal_known !== "true" && f.g_withdrawal_days.trim() !== "") e.g_withdrawal_days = "Only when a source states it";
  return e;
}
