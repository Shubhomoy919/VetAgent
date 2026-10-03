import { motion } from "motion/react";
import type { Stamp as StampKind } from "../api/runs";
import "./Stamp.css";

const TONE: Record<StampKind, "good" | "danger" | "info"> = {
  CORRECT: "good",
  "FALSE-SAFE": "danger",
  "UNDER-TRIAGE": "danger",
  "MISSED ESCALATION": "danger",
  "WITHDRAWAL ERROR": "danger",
  ESCALATED: "info",
};

/** Verdict stamp: uppercase mono, 2px border, rotated about −3°, stamps down on mount. */
export function Stamp({ kind, delay = 0 }: { kind: StampKind; delay?: number }) {
  return (
    <motion.span
      className="stamp"
      data-tone={TONE[kind]}
      initial={{ opacity: 0, scale: 1.5, rotate: -9 }}
      animate={{ opacity: 1, scale: 1, rotate: -3 }}
      transition={{ duration: 0.22, ease: [0.2, 0.8, 0.2, 1], delay }}
    >
      {kind}
    </motion.span>
  );
}
