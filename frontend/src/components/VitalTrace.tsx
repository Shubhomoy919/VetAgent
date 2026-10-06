import type { KeyboardEvent } from "react";
import type { TraceStep } from "../api/runs";
import "./VitalTrace.css";

/** Spike label for each tool / check. */
const LABEL: Record<string, string> = {
  search_guidelines: "SEARCH",
  lookup_drug_safety: "DOSE",
  lookup_withdrawal: "WDL",
  get_patient_record: "RECORD",
};

const STEP_W = 28;
const BASE = 30;
const PAD = 8;

type Kind = "beat" | "spike" | "flat";

function classify(s: TraceStep): { kind: Kind; label: string | null } {
  if (s.kind === "retry") return { kind: "flat", label: null };
  if (s.kind === "tool") return { kind: "spike", label: LABEL[s.name] ?? s.name.slice(0, 6).toUpperCase() };
  if (s.kind === "verify") return { kind: "spike", label: "VERIFY" };
  if (s.kind === "rule") return { kind: "spike", label: "RULE" };
  if (s.kind === "owner") return { kind: "spike", label: "ASK" };
  return { kind: "beat", label: null };
}

function segPath(kind: Kind, x: number): string {
  if (kind === "spike") return `M${x} ${BASE}h7l3 -21l3.5 27l2.5 -6h12`;
  if (kind === "beat") return `M${x} ${BASE}h9l2.5 -6l3 9l2 -3h11.5`;
  return `M${x} ${BASE}h${STEP_W}`;
}

interface Props {
  steps: TraceStep[];
  status: "idle" | "queued" | "running" | "done" | "error";
  /** Click / Enter on a spike: jump to that step in the lab log. */
  onStep?: (index: number) => void;
}

/** Vital-signs trace: an ECG-style line at the top of a condition card. Each model step is a small
 *  beat, each tool call a taller labelled spike (SEARCH, DOSE, RECORD, VERIFY, RULE), an error a flat
 *  madder segment, the final answer a settle mark. Segments draw in as SSE steps arrive. */
export function VitalTrace({ steps, status, onStep }: Props) {
  const segs = steps.map(classify);
  const n = segs.length;
  const end = PAD + n * STEP_W;
  const width = Math.max(end + 40, 200);
  const settled = status === "done";
  const failed = status === "error";
  const summary =
    n === 0
      ? status === "running" || status === "queued"
        ? "Vital signs: waiting for the first step"
        : "Vital signs: not run"
      : `Vital signs: ${n} step${n === 1 ? "" : "s"} — ${segs.map((s) => s.label ?? (s.kind === "flat" ? "retry" : "model")).join(", ")}${settled ? ", answer" : failed ? ", error" : ""}`;

  const key = (i: number) => (e: KeyboardEvent<SVGGElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onStep?.(i);
    }
  };

  return (
    <div className="vt" data-status={status}>
      <svg className="vt-svg" viewBox={`0 0 ${width} 40`} width={width} height={40} role="group" aria-label={summary}>
        <line className="vt-base" x1={0} x2={width} y1={BASE} y2={BASE} />
        <path className="vt-seg" d={`M0 ${BASE}h${PAD}`} pathLength={1} />
        {segs.map((s, i) => {
          const x = PAD + i * STEP_W;
          return (
            <g
              key={i}
              className="vt-step"
              data-kind={s.kind}
              style={{ ["--i" as string]: Math.min(i, 10) }}
              {...(s.kind === "spike" && onStep
                ? { role: "button", tabIndex: 0, "aria-label": `Step ${i + 1}: ${s.label}. Show in the lab log`, onClick: () => onStep(i), onKeyDown: key(i) }
                : { "aria-hidden": true })}
            >
              <path className="vt-seg" d={segPath(s.kind, x)} pathLength={1} />
              {s.label && (
                <text className="vt-label" x={x + 10} y={6}>
                  {s.label}
                </text>
              )}
              {s.kind === "spike" && <rect className="vt-hit" x={x + 2} y={0} width={18} height={40} />}
            </g>
          );
        })}
        {settled && (
          <g className="vt-step" data-kind="settle" style={{ ["--i" as string]: Math.min(n, 10) }} aria-hidden="true">
            <path className="vt-seg" d={`M${end} ${BASE}l4 -3l4 4l4 -1.5l4 0.5h10`} pathLength={1} />
            <rect className="vt-settle" x={end + 28} y={BASE - 3} width={6} height={6} />
          </g>
        )}
        {failed && (
          <g className="vt-step" data-kind="flat" style={{ ["--i" as string]: Math.min(n, 10) }} aria-hidden="true">
            <path className="vt-seg" d={`M${end} ${BASE}h36`} pathLength={1} />
          </g>
        )}
        {status === "running" && <circle className="vt-head" cx={end} cy={BASE} r={2.5} />}
      </svg>
    </div>
  );
}
