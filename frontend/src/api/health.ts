import { useQuery } from "@tanstack/react-query";

/** Mirrors backend/app/api/health.py::Health */
export interface Benchmark {
  version: string;
  hash: string;
  short_hash: string;
  frozen: boolean;
  frozen_on: string;
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  environment: "development" | "production";
  /** The visitor's access: public (read-only) or admin (unlocked with the access code). */
  mode: "public" | "admin";
  access_required: boolean;
  /** Whether answers come from a live model or the demo provider. */
  llm_mode: "live" | "demo";
  provider: "gemini" | "openai_compatible" | "demo";
  configured_provider: "gemini" | "openai_compatible" | "demo";
  model: string;
  key_present: boolean;
  pdf_path: string;
  pdf_loaded: boolean;
  pages: number;
  chunks: number;
  counts: { cases: number; drugs: number; runs: number };
  benchmark: Benchmark | null;
  database: { ok: boolean; engine: "sqlite" };
  data_errors: string[];
}

export async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health", { credentials: "same-origin" });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`GET /api/health → ${res.status} ${res.statusText}${body ? `: ${body.slice(0, 200)}` : ""}`);
  }
  return (await res.json()) as Health;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: 1,
  });
}
