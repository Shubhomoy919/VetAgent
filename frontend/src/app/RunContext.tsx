/* Owns the active run: starts it, follows its SSE stream and keeps live per-condition state. */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import {
  cancelRun,
  getActiveRun,
  resultKey,
  startRun,
  type ConditionId,
  type ResultSummary,
  type RunSummary,
  type StartRunBody,
  type TraceStep,
} from "../api/runs";

import { RunContextObj, type LiveEntry } from "./runState";

interface KeyData {
  case_id: string;
  condition: ConditionId;
  interview: boolean;
}

export function RunProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [run, setRun] = useState<RunSummary | null>(null);
  const [live, setLive] = useState<Record<string, LiveEntry>>({});
  const [starting, setStarting] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  const patch = useCallback((key: string, fn: (prev: LiveEntry | undefined) => LiveEntry) => {
    setLive((prev) => ({ ...prev, [key]: fn(prev[key]) }));
  }, []);

  const follow = useCallback(
    (summary: RunSummary) => {
      sourceRef.current?.close();
      setRun(summary);
      const es = new EventSource(`/api/runs/${summary.run_id}/events`);
      sourceRef.current = es;

      const parse = <T,>(e: MessageEvent): T => JSON.parse(e.data as string) as T;
      const keyOf = (d: KeyData) => resultKey(d.case_id, d.condition, d.interview);

      es.addEventListener("run_started", (e) => {
        const s = parse<RunSummary>(e as MessageEvent);
        setRun(s);
        setLive((prev) => {
          const next = { ...prev };
          for (const cid of s.case_ids)
            for (const cond of s.conditions) next[resultKey(cid, cond, s.interview)] = { status: "queued", steps: [] };
          return next;
        });
      });
      es.addEventListener("result_started", (e) => {
        const d = parse<KeyData>(e as MessageEvent);
        patch(keyOf(d), () => ({ status: "running", steps: [] }));
      });
      es.addEventListener("step", (e) => {
        const d = parse<KeyData & { step: TraceStep }>(e as MessageEvent);
        patch(keyOf(d), (prev) => ({ status: "running", steps: [...(prev?.steps ?? []), d.step] }));
      });
      es.addEventListener("result_done", (e) => {
        const d = parse<KeyData & { result: ResultSummary; n_done: number; n_total: number }>(e as MessageEvent);
        patch(keyOf(d), () => ({
          status: d.result.status === "ok" ? "done" : "error",
          steps: d.result.trace ?? [],
          result: d.result,
        }));
        setRun((r) => (r ? { ...r, n_done: d.n_done } : r));
      });
      es.addEventListener("run_error", (e) => {
        const d = parse<{ error: string }>(e as MessageEvent);
        toast.error(`Run failed: ${d.error}`);
      });
      es.addEventListener("run_done", (e) => {
        const s = parse<RunSummary>(e as MessageEvent);
        setRun(s);
        es.close();
        // anything still queued did not run
        setLive((prev) => {
          const next = { ...prev };
          for (const [k, v] of Object.entries(next)) if (v.status === "queued" || v.status === "running") delete next[k];
          return next;
        });
        void qc.invalidateQueries({ queryKey: ["latest-results"] });
        void qc.invalidateQueries({ queryKey: ["health"] });
        const label = { done: "Run finished", done_with_errors: "Run finished with errors", cancelled: "Run cancelled", failed: "Run failed", quota_exhausted: "Run stopped: daily quota exhausted", running: "" }[s.status];
        toast(`${label} · ${s.n_done}/${s.n_total}`);
      });
      es.onerror = () => {
        // EventSource retries automatically; once the run is done the server closes the stream.
        if (es.readyState === EventSource.CLOSED) sourceRef.current = null;
      };
    },
    [patch, qc],
  );

  // Re-attach to a run that is still going (e.g. after a page reload).
  useEffect(() => {
    let alive = true;
    getActiveRun()
      .then((a) => {
        if (alive && a) follow(a);
      })
      .catch(() => {
        // backend offline: the top bar already shows it
      });
    return () => {
      alive = false;
      sourceRef.current?.close();
    };
  }, [follow]);

  const start = useCallback(
    async (body: StartRunBody) => {
      setStarting(true);
      try {
        follow(await startRun(body));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e));
      } finally {
        setStarting(false);
      }
    },
    [follow],
  );

  const cancel = useCallback(async () => {
    if (!run || run.status !== "running") return;
    try {
      await cancelRun(run.run_id);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }, [run]);

  const value = useMemo(() => ({ run, live, start, cancel, starting }), [run, live, start, cancel, starting]);
  return <RunContextObj.Provider value={value}>{children}</RunContextObj.Provider>;
}

