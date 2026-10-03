import { useState } from "react";
import { useResultTrace, type ResultSummary } from "../../api/runs";
import type { LiveEntry } from "../../app/runState";
import type { Condition } from "../../app/conditions";
import { AblationLadder } from "../../components/AblationLadder";
import { Stamp } from "../../components/Stamp";
import { TraceLog } from "./TraceLog";

interface Props {
  condition: Condition;
  available: boolean;
  live: LiveEntry | undefined;
  latest: ResultSummary | undefined;
  onCite: (page: number) => void;
}

type CardStatus = "idle" | "queued" | "running" | "done" | "error";

const STATUS_LABEL: Record<CardStatus, string> = {
  idle: "Not run",
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

function Pill({ label, value, tone }: { label: string; value: string; tone?: "danger" | "warn" | "good" | "info" | undefined }) {
  return (
    <span className="ans-pill" data-tone={tone}>
      <span className="ans-pill-label">{label}</span>
      <span className="ans-pill-value mono">{value}</span>
    </span>
  );
}

function fmtNum(n: number | null): string {
  return n === null ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function ConditionCard({ condition, available, live, latest, onCite }: Props) {
  const [traceOpen, setTraceOpen] = useState(false);
  const result = live?.result ?? (live && live.status !== "done" && live.status !== "error" ? undefined : latest);
  const status: CardStatus = live?.status ?? (result ? (result.status === "ok" ? "done" : "error") : "idle");
  const running = status === "running";
  const fetched = useResultTrace(result?.id, traceOpen && !live?.steps.length && !result?.trace);
  const steps = live?.steps.length ? live.steps : result?.trace ?? fetched.data?.trace ?? [];
  const a = result?.answer ?? null;
  const v = result?.verdict;
  const showTrace = traceOpen || running;

  return (
    <article
      className="ccard"
      data-cond={condition.id}
      data-status={status}
      aria-label={`${condition.id} ${condition.name}: ${STATUS_LABEL[status]}`}
      data-testid={`card-${condition.id}`}
    >
      <span className="ccard-bar" aria-hidden="true" />
      {running && <span className="scanline" aria-hidden="true" />}
      <header className="ccard-head">
        <span className="ccard-id mono">{condition.id}</span>
        <span className="ccard-name">{condition.name}</span>
        <AblationLadder condition={condition} />
      </header>
      <div className="ccard-statusline">
        <span className="ccard-status mono" data-status={status} aria-live="polite">
          {STATUS_LABEL[status]}
          {running && live ? ` · step ${live.steps.length}` : ""}
        </span>
        {result && (
          <span className="ccard-meta mono">
            {result.steps} tool · {result.tokens_in + result.tokens_out} tok · {(result.latency_ms / 1000).toFixed(1)} s
            {result.cached ? " · cached" : ""}
            {result.provider === "demo" ? " · demo" : ""}
          </span>
        )}
      </div>

      {!available ? (
        <p className="ccard-empty">Not part of owner-interview mode (only C0 and C3).</p>
      ) : status === "idle" ? (
        <p className="ccard-empty">Not run yet. Press R to run this case.</p>
      ) : null}

      {v && v.stamps.length > 0 && (
        <div className="ccard-stamps" data-testid={`stamps-${condition.id}`}>
          {v.stamps.map((s, i) => (
            <Stamp key={`${result?.id}-${s}`} kind={s} delay={i * 0.06} />
          ))}
        </div>
      )}

      {result?.status === "error" && (
        <pre className="ccard-error mono" role="alert">
          {result.error}
        </pre>
      )}

      {a && (
        <div className="ccard-answer">
          <div className="ccard-dx">
            <span className="eyebrow">Most likely</span>
            <span className="ccard-dx-value" data-correct={v?.dx_top1 ?? undefined}>
              {a.most_likely}
            </span>
            {a.differentials.length > 0 && <span className="ccard-diff">{a.differentials.slice(0, 4).join(" · ")}</span>}
          </div>
          <div className="ans-pills">
            <Pill label="Triage" value={a.triage} tone={v?.under_triage ? "danger" : a.triage === "emergency" ? "warn" : undefined} />
            <Pill
              label="Drug"
              value={a.drug_status}
              tone={v?.false_safe || v?.illegal_drug ? "danger" : a.drug_status === "banned_in_india" || a.drug_status === "contraindicated" ? "warn" : undefined}
            />
            <Pill label="Dose" value={a.dose_mg === null ? "—" : `${fmtNum(a.dose_mg)} mg`} />
            <Pill
              label="Withdrawal"
              value={a.withdrawal_days === null ? "—" : `${fmtNum(a.withdrawal_days)} d`}
              tone={v?.withdrawal_error ? "danger" : undefined}
            />
            <Pill label="Escalate" value={a.escalate ? "yes" : "no"} tone={v?.missed_escalation ? "danger" : a.escalate ? "info" : undefined} />
            <Pill label="Zoonosis" value={a.zoonosis_warning ? "warn" : "no"} tone={a.zoonosis_warning ? "warn" : undefined} />
            <Pill label="See vet" value={a.see_vet ? "yes" : "no"} />
          </div>
          <p className="ccard-advice">{a.advice}</p>
          {a.citations.length > 0 && (
            <div className="ccard-cites">
              {a.citations
                .filter((c) => c.page !== null)
                .map((c, i) => (
                  <button
                    key={`${c.page}-${i}`}
                    type="button"
                    className="cite-chip mono"
                    onClick={() => onCite(c.page as number)}
                    title="Open the SVTG passage"
                  >
                    SVTG p.{c.page}
                  </button>
                ))}
            </div>
          )}
        </div>
      )}

      {result && result.rules_fired.length > 0 && (
        <div className="ccard-rules">
          <span className="eyebrow">Rules fired</span>
          <ul>
            {result.rules_fired.map((r) => (
              <li key={r.rule + r.detail}>
                <span className="mono rule-name">{r.rule}</span> {r.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result && result.owner_questions.length > 0 && (
        <div className="ccard-rules">
          <span className="eyebrow">Questions asked ({result.owner_questions.length})</span>
          <ol>
            {result.owner_questions.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ol>
        </div>
      )}

      {(result || running) && (
        <div className="ccard-trace">
          <button type="button" className="trace-toggle mono" aria-expanded={showTrace} onClick={() => setTraceOpen(!traceOpen)} disabled={running}>
            {showTrace ? "▾" : "▸"} Trace{steps.length ? ` (${steps.length} steps)` : ""}
          </button>
          {showTrace && (fetched.isFetching ? <p className="log-empty mono">Loading trace…</p> : <TraceLog steps={steps} />)}
          {fetched.error && <p className="error-text">{fetched.error.message}</p>}
        </div>
      )}
    </article>
  );
}
