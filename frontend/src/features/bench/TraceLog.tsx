import { AnimatePresence, motion, type MotionStyle } from "motion/react";
import { useState } from "react";
import type { TraceStep } from "../../api/runs";

const KIND_LABEL: Record<TraceStep["kind"], string> = {
  llm: "MODEL",
  tool: "TOOL",
  owner: "OWNER",
  retry: "RETRY",
  verify: "VERIFY",
  rule: "RULE",
  cache: "CACHE",
};

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 1);
}

function StepRow({ step, maxLatency, order }: { step: TraceStep; maxLatency: number; order: number }) {
  const [open, setOpen] = useState(false);
  const tokens = step.tokens_in || step.tokens_out ? `${step.tokens_in}→${step.tokens_out} tok` : "";
  return (
    <motion.li
      className="log-step"
      data-kind={step.kind}
      style={{ "--i": Math.min(order, 12) } as unknown as MotionStyle}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.12, delay: Math.min(order, 12) * 0.05 }}
    >
      <span className="log-index mono" aria-hidden="true">
        {step.index || "·"}
      </span>
      <button type="button" className="log-head" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="log-kind mono">{KIND_LABEL[step.kind]}</span>
        <span className="log-name mono">{step.name}</span>
        <span className="log-meta mono">
          {step.latency_ms} ms{tokens && ` · ${tokens}`}
        </span>
      </button>
      {maxLatency > 0 && (
        <span className="log-lat" aria-hidden="true">
          <motion.span
            initial={{ scaleX: 0 }}
            animate={{ scaleX: Math.max(step.latency_ms / maxLatency, 0.01) }}
            transition={{ duration: 0.26, ease: [0.2, 0.8, 0.2, 1], delay: 0.06 }}
          />
        </span>
      )}
      {step.note && !open && <p className="log-note">{step.note}</p>}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            className="log-detail"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
          >
            {step.note && <p className="log-note">{step.note}</p>}
            <div className="log-io">
              <span className="eyebrow">Input</span>
              <pre className="mono">{show(step.input)}</pre>
              <span className="eyebrow">Output</span>
              <pre className="mono">{show(step.output)}</pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

/** Lab-log trace: numbered vertical timeline of model calls, tool readouts and rules. */
export function TraceLog({ steps }: { steps: TraceStep[] }) {
  if (steps.length === 0) return <p className="log-empty mono">No steps recorded.</p>;
  const maxLatency = Math.max(...steps.map((s) => s.latency_ms || 0));
  return (
    <ol className="log">
      {steps.map((s, i) => (
        <StepRow key={`${s.index}-${s.kind}-${s.name}-${i}`} step={s} maxLatency={maxLatency} order={i} />
      ))}
    </ol>
  );
}
