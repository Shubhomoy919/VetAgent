import { motion } from "motion/react";
import { LADDER_STEPS, type Condition } from "../app/conditions";
import "./AblationLadder.css";

interface Props {
  condition: Condition;
  /** Show step names beside the switches. */
  labelled?: boolean;
  /** Larger switches (Study Design, empty states). */
  size?: "sm" | "lg";
}

const KNOB_TRAVEL = { sm: 7, lg: 12 } as const;

/** 7. Ablation ladder as a row of hardware toggles: Retrieval / Tools / Verify / Guardrail.
 *  "On" switches flip across with a short click-like overshoot, one after another. */
export function AblationLadder({ condition, labelled = false, size = "sm" }: Props) {
  const on = LADDER_STEPS.filter((s) => condition.ladder[s]);
  const label = on.length ? `${condition.id} uses ${on.join(", ")}` : `${condition.id} uses no components`;
  const travel = KNOB_TRAVEL[size];
  return (
    <ol className="ladder" data-size={size} data-labelled={labelled} data-cond={condition.id} aria-label={label}>
      {LADDER_STEPS.map((step, i) => {
        const isOn = condition.ladder[step];
        return (
          <li key={step} className="ladder-step" data-on={isOn} title={`${step}: ${isOn ? "on" : "off"}`}>
            <span className="switch-track" aria-hidden="true">
              <motion.span
                className="switch-knob"
                initial={{ x: 0 }}
                animate={isOn ? { x: [0, travel + 1.5, travel] } : { x: 0 }}
                transition={{ duration: 0.2, times: [0, 0.7, 1], ease: [0.2, 0.8, 0.2, 1], delay: 0.08 + i * 0.07 }}
              />
            </span>
            {labelled && <span className="ladder-label">{step}</span>}
          </li>
        );
      })}
    </ol>
  );
}
