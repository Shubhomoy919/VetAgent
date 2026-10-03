import { createContext, useContext } from "react";
import type { RunSummary, StartRunBody, TraceStep, ResultSummary } from "../api/runs";

export interface LiveEntry {
  status: "queued" | "running" | "done" | "error";
  steps: TraceStep[];
  result?: ResultSummary;
}

export interface RunCtx {
  run: RunSummary | null;
  live: Record<string, LiveEntry>;
  start: (body: StartRunBody) => Promise<void>;
  cancel: () => Promise<void>;
  starting: boolean;
}

export const RunContextObj = createContext<RunCtx | null>(null);

export function useRun(): RunCtx {
  const v = useContext(RunContextObj);
  if (!v) throw new Error("useRun must be used inside <RunProvider>");
  return v;
}
