import { QUESTION_TYPE_LABEL, speciesCode, type QuestionType } from "../api/cases";
import "./Tags.css";

/** Luggage-tag case ID: punched hole, species colour stripe, mono ID. */
export function SpecimenTag({ caseId, size = "md" }: { caseId: string; size?: "md" | "lg" }) {
  const code = speciesCode(caseId);
  return (
    <span className="specimen-tag" data-species={code} data-size={size}>
      <span className="specimen-hole" aria-hidden="true" />
      <span className="specimen-id">{caseId}</span>
    </span>
  );
}

export function TypePill({ type }: { type: QuestionType }) {
  return (
    <span className="type-pill" data-type={type}>
      {QUESTION_TYPE_LABEL[type]}
    </span>
  );
}

export function UnverifiedTag({ title = "Not yet verified by a veterinarian" }: { title?: string }) {
  return (
    <span className="unverified-tag" title={title}>
      Unverified
    </span>
  );
}
