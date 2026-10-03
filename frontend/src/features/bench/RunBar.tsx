import { useHealth } from "../../api/health";
import { INTERVIEW_CONDITIONS } from "../../api/runs";
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
  const { run, start, cancel, starting } = useRun();
  const { data: health } = useHealth();
  const running = run?.status === "running";
  const perCase = interview ? INTERVIEW_CONDITIONS.length : 5;
  const busy = running || starting;

  const go = (ids: string[]) => {
    if (ids.length === 0) return;
    const total = ids.length * perCase;
    if (health?.mode === "live" && total > 10) {
      const ok = window.confirm(
        `Run ${ids.length} case${ids.length > 1 ? "s" : ""} × ${perCase} conditions = ${total} live model runs on ${health.model}? This uses API quota.`,
      );
      if (!ok) return;
    }
    void start({ case_ids: ids, interview, force });
  };

  const pct = run && run.n_total ? Math.round((run.n_done / run.n_total) * 100) : 0;

  return (
    <div className="runbar" data-running={running} role="toolbar" aria-label="Run controls">
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
        <label className="toggle" title="Hide the case behind an owner simulator (C0 and C3 only)">
          <input type="checkbox" checked={interview} onChange={(e) => setInterview(e.target.checked)} disabled={busy} />
          Owner interview
        </label>
      </div>
      <div className="runbar-progress" aria-live="polite">
        {run && (
          <>
            <span className="mono runbar-count">
              {run.status === "running" ? "Running" : { done: "Done", done_with_errors: "Done (errors)", cancelled: "Cancelled", failed: "Failed", quota_exhausted: "Quota stop" }[run.status]}{" "}
              {run.n_done}/{run.n_total}
            </span>
            <span
              className="progress"
              role="progressbar"
              aria-label="Run progress"
              aria-valuemin={0}
              aria-valuemax={run.n_total}
              aria-valuenow={run.n_done}
            >
              <span className="progress-fill" style={{ width: `${pct}%` }} />
            </span>
          </>
        )}
        <button type="button" className="btn btn-danger" disabled={!running} onClick={() => void cancel()}>
          Cancel
        </button>
      </div>
      {running && <span className="scanline scanline-bar" aria-hidden="true" />}
    </div>
  );
}
