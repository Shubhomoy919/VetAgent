import type { CSSProperties } from "react";
import { LADDER_STEPS, type Condition } from "../app/conditions";
import "./AblationLadder.css";

interface Props {
  condition: Condition;
  /** Show step names under the dots. */
  labelled?: boolean;
}

export function AblationLadder({ condition, labelled = false }: Props) {
  const on = LADDER_STEPS.filter((s) => condition.ladder[s]);
  const label = on.length ? `${condition.id} uses ${on.join(", ")}` : `${condition.id} uses no components`;
  return (
    <ol
      className="ladder"
      aria-label={label}
      style={{ "--cond": `var(--${condition.id.toLowerCase()})` } as CSSProperties}
    >
      {LADDER_STEPS.map((step) => (
        <li key={step} className="ladder-step" data-on={condition.ladder[step]} title={step}>
          <span className="ladder-dot" aria-hidden="true" />
          {labelled && <span className="ladder-label">{step}</span>}
        </li>
      ))}
    </ol>
  );
}
