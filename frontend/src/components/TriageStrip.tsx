import type { Triage } from "../api/cases";
import "./TriageStrip.css";

const LEVELS: Triage[] = ["routine", "urgent", "emergency"];
const LABEL: Record<Triage, string> = { routine: "Routine", urgent: "Urgent", emergency: "Emergency" };

/** Triage strip: routine / urgent / emergency as a 3-segment instrument strip with the answer lit.
 *  When the answer under-triages, a madder notch marks where the gold answer sits. */
export function TriageStrip({ value, gold, under = false, diff = false }: { value: Triage; gold?: Triage | undefined; under?: boolean; diff?: boolean | undefined }) {
  const label = `Triage: ${value}${under && gold ? `, under-triaged; gold answer ${gold}` : ""}`;
  return (
    <div className="triage" role="img" aria-label={label} data-diff={diff || undefined} data-testid="triage-strip">
      {LEVELS.map((lvl) => (
        <span key={lvl} className="triage-seg" data-level={lvl} data-on={lvl === value}>
          {LABEL[lvl]}
          {under && gold === lvl && <span className="triage-notch" aria-hidden="true" />}
        </span>
      ))}
    </div>
  );
}
