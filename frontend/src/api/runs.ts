import { useQuery } from "@tanstack/react-query";
import type { DrugStatus, Triage } from "./cases";

export type RunStatus = "running" | "done" | "done_with_errors" | "cancelled" | "failed" | "quota_exhausted" | "budget_exhausted" | "interrupted";

/** One wording for run states everywhere (top bar, run bar, toasts, Runs table). */
export const RUN_STATUS_LABEL: Record<RunStatus, string> = {
  running: "Running",
  done: "Done",
  done_with_errors: "Done with errors",
  cancelled: "Cancelled",
  failed: "Failed",
  quota_exhausted: "Stopped: provider quota",
  budget_exhausted: "Stopped: daily budget",
  interrupted: "Interrupted",
};

export interface Budget {
  cap: number;
  used: number;
  remaining: number | null;
  exhausted: boolean;
  max_cases_per_run: number;
}

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
  /** "timeout": the step did not finish within the per-request limit; retry it. */
  status: "ok" | "error" | "timeout";
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
  status: RunStatus;
  n_done: number;
  n_total: number;
  case_ids: string[];
  conditions: ConditionId[];
  interview: boolean;
  force: boolean;
  provider: string;
  model: string;
  /** Steps that already have a result (returned by /runs/active and /finish, so a reloaded page can continue). */
  done?: { case_id: string; condition: ConditionId }[];
}

export interface StepDone {
  case_id: string;
  condition: ConditionId;
  interview: boolean;
  result: ResultSummary;
  n_done: number;
  n_total: number;
  /** Set when the run had to stop after this step. */
  stop: "quota" | "budget" | null;
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
  source: { title: string; url: string };
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
    // The server's message is written for people (budget, access code, limits); show it as is.
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export const startRun = (body: StartRunBody) => request<RunSummary>("POST", "/api/runs", body);
export const finishRun = (id: string, cancelled = false) => request<RunSummary>("POST", `/api/runs/${id}/finish`, { cancelled });

export class StepHttpError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

/** Run one case through one condition: one request, which must finish inside the server's time limit.
 *  The server streams the agent steps as server-sent events; if a proxy returns plain JSON instead, the same
 *  events arrive at the end. Either way `onEvent` sees result_started, step…, result_done (and run_error). */
export async function runStep(
  runId: string,
  caseId: string,
  condition: ConditionId,
  onEvent: (type: string, data: unknown) => void,
  signal?: AbortSignal,
): Promise<StepDone | null> {
  const res = await fetch(`/api/runs/${runId}/step`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ case_id: caseId, condition }),
    signal: signal ?? null,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (data.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // non-JSON body (e.g. the platform's own timeout page)
    }
    throw new StepHttpError(detail, res.status);
  }
  let done: StepDone | null = null;
  const handle = (type: string, data: unknown) => {
    if (type === "result_done") done = data as StepDone;
    onEvent(type, data);
  };
  if ((res.headers.get("content-type") ?? "").includes("text/event-stream") && res.body) {
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = "";
    for (;;) {
      const { value, done: end } = await reader.read();
      if (value) buf += value;
      let cut: number;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, cut);
        buf = buf.slice(cut + 2);
        let type = "message";
        const data: string[] = [];
        for (const line of block.split("\n")) {
          if (line.startsWith("event: ")) type = line.slice(7);
          else if (line.startsWith("data: ")) data.push(line.slice(6));
        }
        if (data.length) handle(type, JSON.parse(data.join("\n")));
      }
      if (end) break;
    }
  } else {
    const body = (await res.json()) as { events?: { type: string; data: unknown }[] };
    for (const e of body.events ?? []) handle(e.type, e.data);
  }
  return done;
}
export const getActiveRun = () => request<RunSummary | null>("GET", "/api/runs/active");
export const getResult = (id: number) => request<ResultSummary>("GET", `/api/results/${id}`);
export const getSvtgPage = (page: number) => request<SvtgPage>("GET", `/api/svtg/pages/${page}`);

export function useBudget(enabled = true) {
  return useQuery({ queryKey: ["budget"], queryFn: () => request<Budget>("GET", "/api/budget"), enabled, refetchInterval: 60_000 });
}

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
