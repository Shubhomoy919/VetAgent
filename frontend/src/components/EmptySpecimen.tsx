import type { ReactNode } from "react";
import "./SpecimenPlate.css";

/** Empty specimen plate: the frame of a plate with nothing mounted yet. */
export function EmptySpecimen({ title, plate = "—", children, testId }: { title: string; plate?: string; children?: ReactNode; testId?: string }) {
  return (
    <div className="plate plate-empty" data-testid={testId}>
      <span className="plate-no mono">Plate {plate}</span>
      <span className="plate-code serif" aria-hidden="true">
        Specimen
      </span>
      <p className="plate-empty-title serif">{title}</p>
      {children && <div className="plate-empty-body">{children}</div>}
    </div>
  );
}
