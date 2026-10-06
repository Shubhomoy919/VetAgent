import { useState } from "react";
import type { Case, CaseDose } from "../../api/cases";
import { DoseDial } from "../../components/DoseDial";
import { SidenoteList, SidenoteRefs } from "../../components/Sidenotes";
import { TriageStrip } from "../../components/TriageStrip";
import { VitalTrace } from "../../components/VitalTrace";
import { useResultTrace, type ResultSummary } from "../../api/runs";
import type { LiveEntry } from "../../app/runState";
import { pickResult, type DiffField } from "./answerDiff";
import type { Condition } from "../../app/conditions";
import { Switchboard } from "../../components/Switchboard";
import { Stamp } from "../../components/Stamp";
import { TraceLog } from "./TraceLog";

interface Props {
  condition: Condition;
  available: boolean;
  live: LiveEntry | undefined;
  latest: ResultSummary | undefined;
  onCite: (page: number) => void;
  /** Compare mode: fields that differ between the compared conditions. */
  diffs?: Set<DiffField> | undefined;
  /** The case under examination (gold triage for the under-triage notch, stamp seeds). */
  caseData?: Case | undefined;
  /** Dose-dial data when the case concerns a drug. */
  dose?: CaseDose | undefined;
}

type CardStatus = "idle" | "queued" | "running" | "done" | "error";


const STATUS_LABEL: Record<CardStatus, string> = {
  idle: "Not run",
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

function Pill({
  label,
  value,
  tone,
  diff,
}: {
  label: string;
  value: string;
  tone?: "danger" | "warn" | "good" | "info" | undefined;
  diff?: boolean | undefined;
}) {
  return (
    <span className="ans-pill" data-tone={tone} data-diff={diff || undefined} title={diff ? "Differs between the compared conditions" : undefined}>
      <span className="ans-pill-label">{label}</span>
      <span className="ans-pill-value mono">{value}</span>
    </span>
  );
}

function fmtNum(n: number | null): string {
  return n === null ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function ConditionCard({ condition, available, live, latest, onCite, diffs, caseData, dose }: Props) {
  const [note, setNote] = useState<number | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const result = pickResult(live, latest);
  const status: CardStatus = live?.status ?? (result ? (result.status === "ok" ? "done" : "error") : "idle");
  const running = status === "running";
  // Fetch the stored trace whenever a result is shown: the vital-signs trace needs it (cached).
  const fetched = useResultTrace(result?.id, !!result && !live?.steps.length && !result?.trace);
  const steps = live?.steps.length ? live.steps : result?.trace ?? fetched.data?.trace ?? [];
  const a = result?.answer ?? null;
  const cites = (a?.citations ?? []).filter((c) => c.page !== null);
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
      <header className="ccard-head" data-lit={running || undefined}>
        <span className="led" data-state={status === "idle" ? undefined : status} aria-hidden="true" />
        <span className="ccard-id mono">{condition.id}</span>
        <span className="ccard-name">{condition.name}</span>
        <Switchboard condition={condition} />
      </header>
      <VitalTrace
        steps={steps}
        status={status}
        onStep={(i) => {
          setTraceOpen(true);
          requestAnimationFrame(() =>
            document.getElementById(`step-${condition.id}-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" }),
          );
        }}
      />
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
            <Stamp key={`${result?.id}-${s}`} kind={s} seed={`${caseData?.case_id ?? ""}-${condition.id}`} delay={i * 0.12} />
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
            <span className="ccard-dx-value" data-correct={v?.dx_top1 ?? undefined} data-diff={diffs?.has("most_likely") || undefined}>
              {a.most_likely}
            </span>
            {a.differentials.length > 0 && <span className="ccard-diff">{a.differentials.slice(0, 4).join(" · ")}</span>}
          </div>
          <TriageStrip value={a.triage} gold={caseData?.gold_answer.triage} under={v?.under_triage === true} diff={diffs?.has("triage")} />
          {dose?.drug && <DoseDial dose={dose} modelDose={a.dose_mg} seed={`${caseData?.case_id ?? ""}-${condition.id}`} />}
          <div className="ans-pills">
            
            <Pill
              label="Drug"
              value={a.drug_status}
              diff={diffs?.has("drug")}
              tone={v?.false_safe || v?.illegal_drug ? "danger" : a.drug_status === "banned_in_india" || a.drug_status === "contraindicated" ? "warn" : undefined}
            />
            <Pill label="Dose" value={a.dose_mg === null ? "—" : `${fmtNum(a.dose_mg)} mg`} diff={diffs?.has("dose")} />
            <Pill
              label="Withdrawal"
              value={a.withdrawal_days === null ? "—" : `${fmtNum(a.withdrawal_days)} d`}
              diff={diffs?.has("withdrawal")}
              tone={v?.withdrawal_error ? "danger" : undefined}
            />
            <Pill label="Escalate" value={a.escalate ? "yes" : "no"} diff={diffs?.has("escalate")} tone={v?.missed_escalation ? "danger" : a.escalate ? "info" : undefined} />
            <Pill label="Zoonosis" value={a.zoonosis_warning ? "warn" : "no"} diff={diffs?.has("zoonosis")} tone={a.zoonosis_warning ? "warn" : undefined} />
            <Pill label="See vet" value={a.see_vet ? "yes" : "no"} diff={diffs?.has("see_vet")} />
          </div>
          <div className="ccard-prose">
            <p className="ccard-advice">
              {a.advice}
              <SidenoteRefs citations={cites} active={note} onToggle={(i) => setNote(note === i ? null : i)} />
            </p>
            <SidenoteList citations={cites} active={note} onCite={onCite} />
          </div>
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
          {showTrace && (fetched.isFetching ? <p className="log-empty mono">Loading trace…</p> : <TraceLog steps={steps} idPrefix={`step-${condition.id}`} />)}
          {fetched.error && <p className="error-text">{fetched.error.message}</p>}
        </div>
      )}
    </article>
  );
}
