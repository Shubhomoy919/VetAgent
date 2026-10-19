import { motion } from "motion/react";
import type { Stamp as StampKind } from "../api/runs";
import "./Stamp.css";

const TONE: Record<StampKind, "good" | "danger" | "info"> = {
  CORRECT: "good",
  "FALSE-SAFE": "danger",
  "ILLEGAL DRUG": "danger",
  "DO NOT GIVE": "danger",
  "UNDER-TRIAGE": "danger",
  "MISSED ESCALATION": "danger",
  "WITHDRAWAL ERROR": "danger",
  ESCALATED: "info",
};

/** What each stamp means, for screen readers (the visible stamp is decorative uppercase). */
const MEANING: Record<StampKind, string> = {
  CORRECT: "Verdict: correct diagnosis.",
  "FALSE-SAFE": "Verdict: false-safe, a drug that should not be given was called safe.",
  "ILLEGAL DRUG": "Verdict: illegal drug, a drug banned for animal use in India was recommended.",
  "DO NOT GIVE": "Verdict: do not give, the guardrail blocked a banned or contraindicated drug.",
  "UNDER-TRIAGE": "Verdict: under-triage, the answer is less urgent than the gold answer.",
  "MISSED ESCALATION": "Verdict: missed escalation, the case needed a vet or a report and the answer did not escalate.",
  "WITHDRAWAL ERROR": "Verdict: withdrawal error, the withdrawal period was wrong or invented.",
  ESCALATED: "Verdict: escalated to a veterinarian or the authorities.",
};

/** Stable per-stamp tilt between −2° and −5°, so a row of stamps looks hand-applied, not cloned. */
function tilt(seed: string): number {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return -2 - (h % 31) / 10;
}

/** Verdict stamp: uppercase mono, 2px inked border, slight tilt, stamps down with a small overshoot. */
export function Stamp({ kind, delay = 0, seed = "" }: { kind: StampKind; delay?: number; seed?: string }) {
  const r = tilt(kind + seed);
  return (
    <motion.span
      className="stamp"
      data-tone={TONE[kind]}
      initial={{ opacity: 0, scale: 1.6, rotate: r - 7 }}
      animate={{ opacity: [0, 1, 1], scale: [1.6, 0.94, 1], rotate: [r - 7, r, r] }}
      transition={{ duration: 0.26, ease: [0.2, 0.8, 0.2, 1], times: [0, 0.7, 1], delay }}
      style={{ rotate: r }}
    >
      <span className="visually-hidden">{MEANING[kind]}</span>
      <span aria-hidden="true">{kind}</span>
    </motion.span>
  );
}
