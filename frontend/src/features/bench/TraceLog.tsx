import { AnimatePresence, motion } from "motion/react";
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

function StepRow({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const tokens = step.tokens_in || step.tokens_out ? `${step.tokens_in}→${step.tokens_out} tok` : "";
  return (
    <motion.li
      className="log-step"
      data-kind={step.kind}
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.18, ease: [0.2, 0.8, 0.2, 1] }}
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
  return (
    <ol className="log">
      {steps.map((s, i) => (
        <StepRow key={`${s.index}-${s.kind}-${s.name}-${i}`} step={s} />
      ))}
    </ol>
  );
}
