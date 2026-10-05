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
      {kind}
    </motion.span>
  );
}
