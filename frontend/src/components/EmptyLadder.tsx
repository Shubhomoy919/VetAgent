import type { ReactNode } from "react";
import { CONDITIONS } from "../app/conditions";
import { Switchboard } from "./Switchboard";
import "./EmptyLadder.css";

/** Empty-state illustration built from the real components: the five conditions as rows of
 *  hardware toggles on a halftone ground, with the call to action in key caps. */
export function EmptyLadder({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="empty-ladder">
      <div className="empty-ladder-figure halftone halftone-soft" aria-hidden="true">
        {CONDITIONS.map((c) => (
          <div key={c.id} className="empty-ladder-row" data-cond={c.id}>
            <span className="empty-ladder-id mono">{c.id}</span>
            <Switchboard condition={c} size="lg" />
          </div>
        ))}
      </div>
      <p className="empty-title serif empty-title-lg">{title}</p>
      {children && <div className="empty-body">{children}</div>}
    </div>
  );
}
