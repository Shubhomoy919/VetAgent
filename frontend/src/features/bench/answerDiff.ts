import type { ResultSummary } from "../../api/runs";
import type { LiveEntry } from "../../app/runState";

/** The result a card shows: the live one while a run is in flight, otherwise the latest stored. */
export function pickResult(live: LiveEntry | undefined, latest: ResultSummary | undefined): ResultSummary | undefined {
  return live?.result ?? (live && live.status !== "done" && live.status !== "error" ? undefined : latest);
}

export type DiffField = "most_likely" | "triage" | "drug" | "dose" | "withdrawal" | "escalate" | "zoonosis" | "see_vet";
type AnswerT = NonNullable<ResultSummary["answer"]>;
/** Answer fields compared across conditions in compare mode. */
export const ANSWER_DIFF_FIELDS: [DiffField, (a: AnswerT) => unknown][] = [
  ["most_likely", (a) => a.most_likely.trim().toLowerCase()],
  ["triage", (a) => a.triage],
  ["drug", (a) => a.drug_status],
  ["dose", (a) => a.dose_mg],
  ["withdrawal", (a) => a.withdrawal_days],
  ["escalate", (a) => a.escalate],
  ["zoonosis", (a) => a.zoonosis_warning],
  ["see_vet", (a) => a.see_vet],
];
