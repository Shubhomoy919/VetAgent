import { motion } from "motion/react";
import type { ReactNode } from "react";
import "./PageHeader.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

/** Page title: plate number above a serif title that inks in from the left. */
export function PageTitle({ plate, children, className = "dp-title" }: { plate: string; children: ReactNode; className?: string }) {
  return (
    <>
      <span className="ph-plate mono" aria-hidden="true">
        PL. {plate} <span className="ph-plate-sep">/</span> VetAgentBench-IN
      </span>
      <motion.h1
        className={`${className} serif ph-title misreg`}
        initial={{ clipPath: "inset(0 100% 0 0)" }}
        animate={{ clipPath: "inset(0 0% 0 0)" }}
        transition={{ duration: 0.26, ease: EASE }}
      >
        {children}
      </motion.h1>
    </>
  );
}
