/* Owns the active run and drives it: the server runs one case through one condition per request (each request
 * ends inside the hosting platform's time limit), so the browser asks for the steps in order, shows each step
 * as it streams in, and closes the run at the end. A reloaded page picks up an unfinished run where it stopped. */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import {
  finishRun,
  getActiveRun,
  resultKey,
  RUN_STATUS_LABEL,
  runStep,
  startRun,
  StepHttpError,
  type ConditionId,
  type RunSummary,
  type StartRunBody,
  type StepDone,
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
  const driving = useRef<string | null>(null);
  const cancelled = useRef(false);
  const abort = useRef<AbortController | null>(null);

  const patch = useCallback((key: string, fn: (prev: LiveEntry | undefined) => LiveEntry) => {
    setLive((prev) => ({ ...prev, [key]: fn(prev[key]) }));
  }, []);

  const drive = useCallback(
    async (summary: RunSummary) => {
      if (driving.current === summary.run_id) return; // already driving this run (React strict mode, two effects)
      driving.current = summary.run_id;
      cancelled.current = false;
      setRun(summary);
      const done = new Set((summary.done ?? []).map((d) => `${d.case_id}|${d.condition}`));
      setLive((prev) => {
        const next = { ...prev };
        for (const cid of summary.case_ids)
          for (const cond of summary.conditions)
            if (!done.has(`${cid}|${cond}`)) next[resultKey(cid, cond, summary.interview)] = { status: "queued", steps: [] };
        return next;
      });

      const keyOf = (d: KeyData) => resultKey(d.case_id, d.condition, d.interview);
      const onEvent = (type: string, raw: unknown) => {
        if (type === "result_started") patch(keyOf(raw as KeyData), () => ({ status: "running", steps: [] }));
        else if (type === "step") {
          const d = raw as KeyData & { step: TraceStep };
          patch(keyOf(d), (prev) => ({ status: "running", steps: [...(prev?.steps ?? []), d.step] }));
        } else if (type === "result_done") {
          const d = raw as StepDone;
          patch(keyOf(d), () => ({
            status: d.result.status === "ok" ? "done" : "error",
            steps: d.result.trace ?? [],
            result: d.result,
          }));
          setRun((r) => (r ? { ...r, n_done: d.n_done } : r));
        } else if (type === "run_error") toast.error((raw as { error: string }).error);
        else if (type === "step_error") {
          const d = raw as { case_id: string; condition: ConditionId; error: string };
          patch(resultKey(d.case_id, d.condition, summary.interview), (prev) => ({ status: "error", steps: prev?.steps ?? [] }));
          toast.error(d.error);
        }
      };

      outer: for (const cid of summary.case_ids) {
        for (const cond of summary.conditions) {
          if (cancelled.current) break outer;
          if (done.has(`${cid}|${cond}`)) continue;
          const ctrl = new AbortController();
          abort.current = ctrl;
          try {
            const result = await runStep(summary.run_id, cid, cond, onEvent, ctrl.signal);
            if (result?.stop) break outer;
          } catch (e) {
            if (cancelled.current) break outer;
            const key = resultKey(cid, cond, summary.interview);
            patch(key, (prev) => ({ status: "error", steps: prev?.steps ?? [] }));
            const message = e instanceof Error ? e.message : String(e);
            // Run closed, budget reached, model changed, not unlocked: nothing further can run.
            if (e instanceof StepHttpError && [401, 404, 409, 429].includes(e.status)) {
              toast.error(message);
              break outer;
            }
            // Network error or the platform cut the request: record and go on with the next step.
            toast.error(`${cid} · ${cond}: ${message}`);
          } finally {
            abort.current = null;
          }
        }
      }

      let final: RunSummary | null = null;
      try {
        final = await finishRun(summary.run_id, cancelled.current);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e));
      }
      driving.current = null;
      setRun((r) => final ?? (r ? { ...r, status: cancelled.current ? "cancelled" : "done" } : r));
      // anything still queued or running did not run
      setLive((prev) => {
        const next = { ...prev };
        for (const [k, v] of Object.entries(next)) if (v.status === "queued" || v.status === "running") delete next[k];
        return next;
      });
      for (const key of ["latest-results", "health", "budget", "runs", "case-results"])
        void qc.invalidateQueries({ queryKey: [key] });
      if (final) toast(`Run ${RUN_STATUS_LABEL[final.status].toLowerCase()} · ${final.n_done}/${final.n_total}`);
    },
    [patch, qc],
  );

  // Continue a run that is still open (e.g. after a page reload).
  useEffect(() => {
    let alive = true;
    getActiveRun()
      .then((a) => {
        if (alive && a) void drive(a);
      })
      .catch(() => {
        // backend offline: the top bar already shows it
      });
    return () => {
      alive = false;
    };
  }, [drive]);

  const start = useCallback(
    async (body: StartRunBody) => {
      setStarting(true);
      let summary: RunSummary | null = null;
      try {
        summary = await startRun(body);
      } catch (e) {
        toast.error(e instanceof Error ? e.message : String(e));
      } finally {
        setStarting(false);
      }
      if (summary) await drive(summary);
    },
    [drive],
  );

  const cancel = useCallback(async () => {
    if (!run || run.status !== "running") return;
    cancelled.current = true;
    abort.current?.abort();
  }, [run]);

  const value = useMemo(() => ({ run, live, start, cancel, starting }), [run, live, start, cancel, starting]);
  return <RunContextObj.Provider value={value}>{children}</RunContextObj.Provider>;
}
