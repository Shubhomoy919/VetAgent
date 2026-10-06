import { useQuery } from "@tanstack/react-query";
import type { DrugStatus, Triage } from "./cases";

export type ConditionId = "C0" | "C1" | "C2" | "C3" | "C4";
export const CONDITION_IDS: ConditionId[] = ["C0", "C1", "C2", "C3", "C4"];
export const INTERVIEW_CONDITIONS: ConditionId[] = ["C0", "C3"];

export interface Answer {
  differentials: string[];
  most_likely: string;
  triage: Triage;
  drug_status: DrugStatus | "n/a";
  dose_mg: number | null;
  withdrawal_days: number | null;
  escalate: boolean;
  zoonosis_warning: boolean;
  see_vet: boolean;
  advice: string;
  citations: Citation[];
}

export interface Citation {
  source: string;
  page: number | null;
}

export type Stamp =
  | "CORRECT"
  | "FALSE-SAFE"
  | "ILLEGAL DRUG"
  | "UNDER-TRIAGE"
  | "MISSED ESCALATION"
  | "WITHDRAWAL ERROR"
  | "ESCALATED"
  | "DO NOT GIVE";

export interface Verdict {
  scored: boolean;
  stamps: Stamp[];
  dx_top1?: boolean;
  dx_top3?: boolean;
  triage_match?: boolean;
  under_triage?: boolean;
  over_triage?: boolean;
  false_safe?: boolean | null;
  illegal_drug?: boolean | null;
  withdrawal_error?: boolean | null;
  missed_escalation?: boolean | null;
  dangerous?: boolean;
}

export interface TraceStep {
  index: number;
  kind: "llm" | "tool" | "owner" | "retry" | "verify" | "rule" | "cache";
  name: string;
  input: unknown;
  output: unknown;
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  note: string;
}

export interface RuleFiring {
  rule: string;
  detail: string;
  changes: Record<string, [unknown, unknown]>;
}

export interface ResultSummary {
  id: number | null;
  case_id: string;
  condition: ConditionId;
  interview: boolean;
  status: "ok" | "error";
  answer: Answer | null;
  error: string | null;
  rules_fired: RuleFiring[];
  owner_questions: string[];
  steps: number;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number | null;
  latency_ms: number;
  cached: boolean;
  verdict: Verdict;
  provider?: string;
  model?: string;
  created_at?: string;
  run_id?: string;
  trace?: TraceStep[];
}

export interface RunSummary {
  run_id: string;
  status: "running" | "done" | "done_with_errors" | "cancelled" | "failed" | "quota_exhausted";
  n_done: number;
  n_total: number;
  case_ids: string[];
  conditions: ConditionId[];
  interview: boolean;
  force: boolean;
  provider: string;
  model: string;
}

export interface StartRunBody {
  case_ids: string[];
  conditions?: ConditionId[];
  interview: boolean;
  force: boolean;
}

export interface SvtgPage {
  page: number;
  printed_page: number | null;
  chunks: { chunk_id: string; section: string; text: string }[];
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // non-JSON body
    }
    throw new Error(`${method} ${url} → ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export const startRun = (body: StartRunBody) => request<RunSummary>("POST", "/api/runs", body);
export const cancelRun = (id: string) => request<{ run_id: string }>("POST", `/api/runs/${id}/cancel`);
export const getActiveRun = () => request<RunSummary | null>("GET", "/api/runs/active");
export const getResult = (id: number) => request<ResultSummary>("GET", `/api/results/${id}`);
export const getSvtgPage = (page: number) => request<SvtgPage>("GET", `/api/svtg/pages/${page}`);

export type LatestResults = Record<string, Partial<Record<ConditionId, ResultSummary>>>;

export function useLatestResults(interview: boolean) {
  return useQuery({
    queryKey: ["latest-results", interview],
    queryFn: () => request<LatestResults>("GET", `/api/results/latest?interview=${interview}`),
  });
}

/** Every stored result for one case across runs, newest first (no traces). */
export function useCaseResults(caseId: string | null) {
  return useQuery({
    queryKey: ["case-results", caseId],
    queryFn: () => request<ResultSummary[]>("GET", `/api/results?case_id=${encodeURIComponent(caseId as string)}`),
    enabled: caseId !== null,
  });
}

export function useResultTrace(id: number | null | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["result", id],
    queryFn: () => getResult(id as number),
    enabled: enabled && typeof id === "number",
    staleTime: Infinity,
  });
}

export function useSvtgPage(page: number | null) {
  return useQuery({
    queryKey: ["svtg-page", page],
    queryFn: () => getSvtgPage(page as number),
    enabled: page !== null,
    staleTime: Infinity,
  });
}

export const resultKey = (caseId: string, cond: ConditionId, interview: boolean) =>
  `${caseId}|${cond}|${interview ? 1 : 0}`;
