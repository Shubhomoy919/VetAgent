import { useQuery } from "@tanstack/react-query";
import type { ConditionId, RunStatus } from "./runs";

export interface Rate {
  k: number;
  n: number;
  rate: number | null;
  lo: number | null;
  hi: number | null;
}

export interface MetricRow {
  key: string;
  label: string;
  better: "higher" | "lower";
  danger: boolean;
  description: string;
  by_condition: Partial<Record<ConditionId, Rate>>;
}

export interface McNemarRow {
  metric: string;
  a: ConditionId;
  b: ConditionId;
  n_pairs: number;
  only_a: number;
  only_b: number;
  p: number | null;
}

export interface BreakdownRow {
  group: string;
  label: string;
  n_cases: number;
  by_condition: Partial<Record<ConditionId, { dx_top1: Rate; dangerous: Rate }>>;
}

export interface Usage {
  results: number;
  errors: number;
  avg_steps: number | null;
  avg_tokens: number | null;
  total_tokens: number;
  avg_latency_ms: number | null;
  total_cost_usd: number | null;
}

export interface RunRow {
  id: string;
  created_at: string;
  label: string;
  provider: string;
  model: string;
  prompt_version: string;
  conditions: ConditionId[];
  case_ids: string[];
  interview: boolean;
  status: RunStatus;
  n_total: number;
  n_done: number;
  finished_at?: string | null;
  temperature?: number | null;
  benchmark_version?: string | null;
  benchmark_hash?: string | null;
}

/** What produced a scorecard: shown on the page and written into every export. */
export interface Provenance {
  disclaimer: string;
  benchmark_version: string;
  benchmark_hash: string;
  run_id: string;
  run_date: string;
  provider: string;
  model: string;
  prompt_version: string;
  temperature: number | null;
  run_benchmark_version: string | null;
  run_benchmark_hash: string | null;
}

export interface Scorecard {
  run: RunRow;
  provenance: Provenance;
  conditions: ConditionId[];
  n_cases: number;
  metrics: MetricRow[];
  mcnemar: McNemarRow[];
  breakdowns: { species: BreakdownRow[]; question_type: BreakdownRow[] };
  usage: Partial<Record<ConditionId, Usage>>;
  warnings: string[];
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: unknown };
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // non-JSON body
    }
    throw new Error(`GET ${url} → ${res.status}: ${detail}`);
  }
  return (await res.json()) as T;
}

export function useScorecard(runId: string | null) {
  return useQuery({
    queryKey: ["scorecard", runId],
    queryFn: () => getJson<Scorecard>(`/api/scorecard${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`),
    retry: false,
  });
}

export function useRuns() {
  return useQuery({ queryKey: ["runs"], queryFn: () => getJson<RunRow[]>("/api/runs?limit=200") });
}

export function pct(r: number | null | undefined, digits = 0): string {
  return r === null || r === undefined ? "—" : `${(r * 100).toFixed(digits)}%`;
}

export function fmtP(p: number | null): string {
  if (p === null) return "n/a";
  if (p < 0.001) return "<0.001";
  return p.toFixed(3);
}
