import type { CSSProperties } from "react";
import { useIsAdmin } from "../../api/auth";
import { useHealth } from "../../api/health";
import { INTERVIEW_CONDITIONS, RUN_STATUS_LABEL, resultKey, useBudget } from "../../api/runs";
import { ReadOnlyNote } from "../../app/Access";
import { useRun } from "../../app/runState";

interface Props {
  caseId: string | null;
  selected: string[];
  allIds: string[];
  interview: boolean;
  force: boolean;
  setInterview: (v: boolean) => void;
  setForce: (v: boolean) => void;
  onOpenCases?: (() => void) | undefined;
}

export function RunBar({ caseId, selected, allIds, interview, force, setInterview, setForce, onOpenCases }: Props) {
  const { run, live, start, cancel, starting } = useRun();
  const { data: health } = useHealth();
  const admin = useIsAdmin();
  const { data: budget } = useBudget(admin);
  const running = run?.status === "running";
  const perCase = interview ? INTERVIEW_CONDITIONS.length : 5;
  const busy = running || starting;

  const go = (ids: string[]) => {
    if (ids.length === 0) return;
    const total = ids.length * perCase;
    if (health?.llm_mode === "live" && total > 10) {
      const ok = window.confirm(
        `Run ${ids.length} case${ids.length > 1 ? "s" : ""} × ${perCase} conditions = ${total} live model runs on ${health.model}? This uses API quota.`,
      );
      if (!ok) return;
    }
    void start({ case_ids: ids, interview, force });
  };

  // Instrument meter: one segment per result (grouped into at most 40 segments for big runs),
  // lit marigold as results land, vermilion for errors.
  const states = run ? run.case_ids.flatMap((cid) => run.conditions.map((c) => live[resultKey(cid, c, run.interview)]?.status ?? "queued")) : [];
  const nSeg = Math.min(states.length, 40);
  const segments = Array.from({ length: nSeg }, (_, i) => {
    const group = states.slice(Math.floor((i * states.length) / nSeg), Math.floor(((i + 1) * states.length) / nSeg));
    if (group.some((s) => s === "error")) return "error";
    if (group.every((s) => s === "done" || s === "error")) return "done";
    if (group.some((s) => s === "running" || s === "done")) return "running";
    return "queued";
  });
  const fraction = run && run.n_total ? run.n_done / run.n_total : 0;

  return (
    <div className="runbar" data-running={running} role="toolbar" aria-label="Run controls">
      {!admin ? (
        <div className="runbar-actions">
          {onOpenCases && (
            <button type="button" className="btn" onClick={onOpenCases} data-testid="open-cases">
              Cases{caseId ? ` · ${caseId}` : ""}
            </button>
          )}
          <ReadOnlyNote what="Run cases" />
        </div>
      ) : (
      <div className="runbar-actions">
        {onOpenCases && (
          <button type="button" className="btn" onClick={onOpenCases} data-testid="open-cases">
            Cases{caseId ? ` · ${caseId}` : ""}
          </button>
        )}
        <button type="button" className="btn btn-primary" disabled={busy || !caseId} onClick={() => caseId && go([caseId])}>
          Run case <kbd>R</kbd>
        </button>
        <button type="button" className="btn" disabled={busy || selected.length === 0} onClick={() => go(selected)}>
          Run selected ({selected.length})
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => go(allIds)}>
          Run all ({allIds.length})
        </button>
        <label className="toggle">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} />
          Force re-run
        </label>
        <details className="runbar-advanced">
          <summary>Advanced</summary>
          <label className="toggle" title="Hide the case behind an owner simulator (C0 and C3 only)">
            <input type="checkbox" checked={interview} onChange={(e) => setInterview(e.target.checked)} disabled={busy} />
            Owner interview (C0 and C3 only)
          </label>
        </details>
        {budget && budget.cap > 0 && (
          <span className={`runbar-budget mono${budget.exhausted ? " is-out" : ""}`} data-testid="budget" title="Live-model tokens used today (UTC) against the daily cap">
            {budget.exhausted ? "Daily budget reached" : `Budget ${budget.used.toLocaleString("en-US")} / ${budget.cap.toLocaleString("en-US")} tokens`}
          </span>
        )}
      </div>
      )}
      <div className="runbar-progress" aria-live="polite">
        {run && (
          <>
            <span className="mono runbar-count">
              {RUN_STATUS_LABEL[run.status]}{" "}
              {run.n_done}/{run.n_total}
            </span>
            <span
              className="meter"
              role="progressbar"
              aria-label="Run progress"
              aria-valuemin={0}
              aria-valuemax={run.n_total}
              aria-valuenow={run.n_done}
              style={{ "--fill": fraction } as CSSProperties}
            >
              {segments.map((st, i) => (
                <span key={i} className="meter-seg" data-state={st} />
              ))}
            </span>
          </>
        )}
        {admin && (
          <button type="button" className="btn btn-danger" disabled={!running} onClick={() => void cancel()}>
            Cancel run
          </button>
        )}
      </div>
      {running && <span className="scanline scanline-bar" aria-hidden="true" />}
    </div>
  );
}
