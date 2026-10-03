import { useQuery } from "@tanstack/react-query";
import type { Case, DrugStatus, Species } from "./cases";

export interface ValidationMeta {
  case_id_pattern: string;
  prefix_species: Record<string, Species[]>;
  weight_ranges: Record<Species, [number, number][]>;
  question_types: string[];
  species: Species[];
  sexes: string[];
  triage: string[];
  drug_status: DrugStatus[];
}

export interface DrugRow {
  species: Species;
  drug: string;
  status: DrugStatus;
  dose_min_mg_per_kg: number | null;
  dose_max_mg_per_kg: number | null;
  milk_withdrawal_days: number | null;
  meat_withdrawal_days: number | null;
  legal_in_india: boolean;
  source: string;
  notes: string;
  verified_by: string;
  verified_on: string;
  verified: boolean;
}

export interface FieldError {
  loc: (string | number)[];
  msg: string;
}

/** An API error carrying the server's per-field validation messages. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public errors: FieldError[] = [],
  ) {
    super(message);
  }
}

async function send<T>(method: string, url: string, body?: unknown, contentType = "application/json"): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": contentType };
    init.body = contentType === "application/json" ? JSON.stringify(body) : (body as string);
  }
  const res = await fetch(url, init);
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // empty or non-JSON body
  }
  if (!res.ok) {
    const d = (data ?? {}) as { detail?: unknown; errors?: FieldError[] };
    const detail = typeof d.detail === "string" ? d.detail : d.detail ? JSON.stringify(d.detail) : res.statusText;
    throw new ApiError(detail, res.status, Array.isArray(d.errors) ? d.errors : []);
  }
  return data as T;
}

export const saveCase = (data: unknown, originalId: string | null) =>
  originalId ? send<Case>("PUT", `/api/cases/${encodeURIComponent(originalId)}`, data) : send<Case>("POST", "/api/cases", data);
export const deleteCase = (id: string) => send<void>("DELETE", `/api/cases/${encodeURIComponent(id)}`);
export const importCases = (items: unknown, mode: "merge" | "replace") =>
  send<{ imported: number; total: number }>("POST", `/api/cases/import?mode=${mode}`, items);

export const saveDrug = (data: unknown, originalKey: string | null) =>
  originalKey
    ? send<DrugRow>("PUT", `/api/drugs?key=${encodeURIComponent(originalKey)}`, data)
    : send<DrugRow>("POST", "/api/drugs", data);
export const deleteDrug = (key: string) => send<void>("DELETE", `/api/drugs?key=${encodeURIComponent(key)}`);
export const importDrugs = (csv: string, mode: "merge" | "replace") =>
  send<{ imported: number; total: number }>("POST", `/api/drugs/import?mode=${mode}`, csv, "text/csv");

export const drugKey = (r: Pick<DrugRow, "species" | "drug">) => `${r.species}|${r.drug.toLowerCase()}`;

export function useMeta() {
  return useQuery({ queryKey: ["validation-meta"], queryFn: () => send<ValidationMeta>("GET", "/api/meta/validation"), staleTime: Infinity });
}

export function useDrugs() {
  return useQuery({ queryKey: ["drugs"], queryFn: () => send<DrugRow[]>("GET", "/api/drugs") });
}

export function errorsByField(errors: FieldError[], map: (loc: string) => string | null): { fields: Record<string, string>; other: string[] } {
  const fields: Record<string, string> = {};
  const other: string[] = [];
  for (const e of errors) {
    const key = map(e.loc.join("."));
    if (key && !fields[key]) fields[key] = e.msg;
    else other.push(e.loc.length ? `${e.loc.join(".")}: ${e.msg}` : e.msg);
  }
  return { fields, other };
}
