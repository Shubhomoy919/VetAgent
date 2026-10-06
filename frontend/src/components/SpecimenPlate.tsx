import type { ReactNode } from "react";
import { formatAge, formatSex, speciesCode, type Case } from "../api/cases";
import { useCaseResults } from "../api/runs";
import { latinName, roman } from "../lib/species";
import { TypePill, SpecimenTag, UnverifiedTag } from "./Tags";
import "./SpecimenPlate.css";

/** Small print registration mark (circle + cross) for plate corners. */
export function RegMark({ corner }: { corner: "tl" | "tr" | "bl" | "br" }) {
  return (
    <svg className="reg-mark" data-corner={corner} viewBox="0 0 14 14" aria-hidden="true" focusable="false">
      <circle cx="7" cy="7" r="3.2" />
      <path d="M7 0v14M0 7h14" />
    </svg>
  );
}

function hhmm(iso: string | undefined): string | null {
  if (!iso) return null;
  const t = iso.split("T")[1];
  return t ? t.slice(0, 5) : null;
}

/** Specimen plate: the case header as a natural-history plate — double-rule frame, plate number in
 *  Roman numerals, species code in large serif, Latin binomial in italic, signalment strip,
 *  registration marks, and a lab-notebook line ("examined 3 times · last run 14:02"). */
export function SpecimenPlate({ c, plateNo, actions }: { c: Case; plateNo: number; actions?: ReactNode }) {
  const s = c.signalment;
  const code = speciesCode(c.case_id);
  const { data: past } = useCaseResults(c.case_id);
  const runs = new Set((past ?? []).map((r) => r.run_id)).size;
  const last = hhmm(past?.[0]?.created_at);
  return (
    <header className="plate plate-frame" data-species={code} data-testid="specimen-plate">
      <RegMark corner="tl" />
      <RegMark corner="tr" />
      <RegMark corner="bl" />
      <RegMark corner="br" />
      <div className="plate-top">
        <span className="plate-no mono">Plate {roman(plateNo)}</span>
        <SpecimenTag caseId={c.case_id} />
        <TypePill type={c.question_type} />
        {!c.vet_verified && <UnverifiedTag />}
        {actions && <span className="plate-actions">{actions}</span>}
      </div>
      <div className="plate-body">
        <span className="plate-code serif misreg" aria-hidden="true">
          {code}
        </span>
        <div className="plate-names">
          <h3 id="case-detail-id" className="plate-latin serif">
            <span className="visually-hidden">Case {c.case_id}: </span>
            {latinName(c)}
          </h3>
          <p className="plate-breed">{s.breed}</p>
        </div>
      </div>
      <dl className="sig-strip plate-strip" aria-label="Signalment">
        <div className="sig-field">
          <dt className="eyebrow">Species</dt>
          <dd>
            <span data-testid="case-species">{c.species}</span>
          </dd>
        </div>
        <div className="sig-field">
          <dt className="eyebrow">Age</dt>
          <dd className="mono">{formatAge(s.age_months)}</dd>
        </div>
        <div className="sig-field">
          <dt className="eyebrow">Sex</dt>
          <dd>
            {formatSex(s.sex)}
            {s.sex === "female" && s.lactating && <span className="sig-sub"> · lactating</span>}
          </dd>
        </div>
        <div className="sig-field">
          <dt className="eyebrow">Weight</dt>
          <dd className="mono">{s.weight_kg} kg</dd>
        </div>
      </dl>
      <p className="plate-log mono" data-testid="plate-log">
        Specimen {c.case_id} · {past === undefined ? "…" : runs === 0 ? "not yet examined" : `examined ${runs} time${runs === 1 ? "" : "s"}`}
        {last ? ` · last run ${last}` : ""}
      </p>
    </header>
  );
}
