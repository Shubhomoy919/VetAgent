import { useQuery } from "@tanstack/react-query";

/** Mirrors backend/app/api/health.py::Health */
export interface Health {
  status: "ok";
  provider: "gemini" | "openai_compatible" | "demo";
  configured_provider: "gemini" | "openai_compatible" | "demo";
  mode: "live" | "demo";
  model: string;
  key_present: boolean;
  pdf_path: string;
  pdf_loaded: boolean;
  pages: number;
  chunks: number;
  counts: { cases: number; drugs: number; runs: number };
}

export async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health");
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
