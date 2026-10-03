/* API client for Runs, Review, Settings and metric metadata. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { Case, GoldAnswer, QuestionType } from "./cases";
import { ApiError, type FieldError } from "./data";
import type { Answer, ConditionId, RuleFiring, Stamp } from "./runs";
import type { Rate, RunRow } from "./scorecard";

async function send<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // empty body
  }
  if (!res.ok) {
    const d = (data ?? {}) as { detail?: unknown; errors?: FieldError[] };
    const detail = typeof d.detail === "string" ? d.detail : d.detail ? JSON.stringify(d.detail) : res.statusText;
    throw new ApiError(detail, res.status, Array.isArray(d.errors) ? d.errors : []);
  }
  return data as T;
}

// ---------- runs ----------

export interface RunListRow extends RunRow {
  tokens: number;
  errors: number;
  cost_usd: number | null;
  finished_at: string | null;
}

export function useRunList() {
  return useQuery({ queryKey: ["runs"], queryFn: () => send<RunListRow[]>("GET", "/api/runs?limit=200") });
}

export interface CompareResult {
  a: RunRow;
  b: RunRow;
  conditions: ConditionId[];
  n_pairs: number;
  metrics: {
    key: string;
    label: string;
    better: "higher" | "lower";
    by_condition: Partial<Record<ConditionId, { a: Rate; b: Rate; delta: number | null }>>;
  }[];
  changes: {
    case_id: string;
    condition: ConditionId;
    a: { status: string; dx_top1: boolean | null; dangerous: boolean | null; stamps: Stamp[] };
    b: { status: string; dx_top1: boolean | null; dangerous: boolean | null; stamps: Stamp[] };
  }[];
}

export function useCompare(a: string | null, b: string | null) {
  return useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => send<CompareResult>("GET", `/api/runs/compare?a=${encodeURIComponent(a ?? "")}&b=${encodeURIComponent(b ?? "")}`),
    enabled: Boolean(a && b),
  });
}

// ---------- review ----------

export type Rating = "acceptable" | "unacceptable" | "unsure";

export interface ReviewItem {
  result_id: number;
  case_id: string;
  condition: ConditionId;
  interview: boolean;
  answer: Answer;
  rules_fired: RuleFiring[];
  case: Pick<Case, "case_id" | "species" | "signalment" | "history" | "owner_narrative" | "clinical_signs" | "question">;
  question_type: QuestionType;
  gold: GoldAnswer;
  auto: { dangerous: boolean; stamps: Stamp[]; dx_top1: boolean };
  review: { rating: Rating; note: string } | null;
}

export interface Agreement {
  n: number;
  agree: number;
  percent: number | null;
  kappa: number | null;
  matrix: { acc_acc: number; acc_unacc: number; unacc_acc: number; unacc_unacc: number };
}

export interface ReviewStats {
  run: RunRow;
  items_total: number;
  reviewers: {
    reviewer: string;
    rated: number;
    unsure: number;
    vs_auto: Agreement;
    acceptable_by_condition: Partial<Record<ConditionId, Rate>>;
  }[];
  pairs: ({ a: string; b: string } & Agreement)[];
}

export function useReviewQueue(runId: string | null, reviewer: string) {
  return useQuery({
    queryKey: ["review-queue", runId, reviewer],
    queryFn: () =>
      send<{ run: RunRow; items: ReviewItem[] }>(
        "GET",
        `/api/review/queue?reviewer=${encodeURIComponent(reviewer)}${runId ? `&run_id=${encodeURIComponent(runId)}` : ""}`,
      ),
    retry: false,
    placeholderData: keepPreviousData, // keep the answer on screen while the reviewer name changes
  });
}

export function useReviewStats(runId: string | null) {
  return useQuery({
    queryKey: ["review-stats", runId],
    queryFn: () => send<ReviewStats>("GET", `/api/review/stats${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`),
    retry: false,
  });
}

export const saveReview = (result_id: number, reviewer: string, rating: Rating, note: string) =>
  send<unknown>("PUT", "/api/review", { result_id, reviewer, rating, note });

export function kappaLabel(k: number | null): string {
  if (k === null) return "undefined";
  if (k < 0) return "poor";
  if (k <= 0.2) return "slight";
  if (k <= 0.4) return "fair";
  if (k <= 0.6) return "moderate";
  if (k <= 0.8) return "substantial";
  return "almost perfect";
}

// ---------- settings ----------

export interface SettingsValues {
  llm_provider: "gemini" | "openai_compatible" | "demo";
  gemini_model: string;
  openai_base_url: string;
  openai_model: string;
  svtg_pdf_path: string;
  temperature: number;
  max_steps: number;
  max_owner_questions: number;
  demo_delay_ms: number;
  price_input_per_mtok: number | null;
  price_output_per_mtok: number | null;
}

export interface SettingsView {
  values: SettingsValues;
  overridden: (keyof SettingsValues)[];
  effective_provider: string;
  mode: "live" | "demo";
  model: string;
  key_present: boolean;
  key_hint: string;
  pdf: { path: string; exists: boolean; loaded: boolean; pages: number };
  overrides_file: string;
}

export interface UsageTotals {
  by_model: { provider: string; model: string; results: number; tokens_in: number; tokens_out: number; cost_usd: number | null; cost_unknown: number }[];
  total_results: number;
  total_tokens: number;
  total_cost_usd: number | null;
}

export interface TestResult {
  ok: boolean;
  provider: string;
  model: string;
  latency_ms: number;
  reply: string | null;
  message: string;
  tokens?: number;
}

export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => send<SettingsView>("GET", "/api/settings") });
}

export function useUsage() {
  return useQuery({ queryKey: ["usage"], queryFn: () => send<UsageTotals>("GET", "/api/settings/usage") });
}

export const saveSettings = (values: Partial<Record<keyof SettingsValues, unknown>>) => send<SettingsView>("PUT", "/api/settings", values);
export const resetSettings = () => send<SettingsView>("DELETE", "/api/settings");
export const testConnection = () => send<TestResult>("POST", "/api/settings/test");

// ---------- metric metadata ----------

export interface MetricMeta {
  key: string;
  label: string;
  better: "higher" | "lower";
  danger: boolean;
  description: string;
}

export function useMetricMeta() {
  return useQuery({ queryKey: ["metric-meta"], queryFn: () => send<MetricMeta[]>("GET", "/api/meta/metrics"), staleTime: Infinity });
}
