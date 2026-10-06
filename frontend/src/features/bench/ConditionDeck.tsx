import { useEffect, useMemo, useRef, useState, type UIEvent } from "react";
import { INTERVIEW_CONDITIONS, resultKey, type ConditionId, type LatestResults } from "../../api/runs";
import { useCaseDose, type Case } from "../../api/cases";
import { useRun } from "../../app/runState";
import { CONDITIONS } from "../../app/conditions";
import { EmptySpecimen } from "../../components/EmptySpecimen";
import { ConditionCard } from "./ConditionCard";
import { ANSWER_DIFF_FIELDS, pickResult, type DiffField } from "./answerDiff";

interface Props {
  caseId: string | null;
  interview: boolean;
  latest: LatestResults | undefined;
  onCite: (page: number) => void;
  /** Narrow screens: show one condition at a time, chosen by the tabs. */
  tabs?: boolean;
  caseData?: Case | undefined;
}

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function ConditionDeck({ caseId, interview, latest, onCite, tabs = false, caseData }: Props) {
  const { data: dose } = useCaseDose(caseId);
  const { live } = useRun();
  const [compare, setCompare] = useState(false);
  const [picked, setPicked] = useState<ConditionId[]>(["C0", "C4"]);
  const [active, setActive] = useState<ConditionId>("C0");
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollTo = (id: ConditionId) => {
    setActive(id);
    scrollRef.current?.querySelector<HTMLElement>(`[data-cond="${id}"]`)?.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
  };

  // 1–5 jump to a condition card.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      const n = Number(e.key);
      if (n >= 1 && n <= 5) {
        const id = CONDITIONS[n - 1]?.id;
        if (!id) return;
        e.preventDefault();
        if (compare) setPicked((p) => (p.includes(id) ? p : [...p.slice(-2), id]));
        else scrollTo(id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [compare]);

  // Compare mode: which answer fields disagree between the compared conditions (marigold underline).
  const diffs = useMemo(() => {
    const out = new Set<DiffField>();
    if (!compare || !caseId) return out;
    const answers = CONDITIONS.filter((c) => picked.includes(c.id))
      .map((c) => pickResult(live[resultKey(caseId, c.id, interview)], latest?.[caseId]?.[c.id])?.answer)
      .filter((a) => a != null);
    if (answers.length < 2) return out;
    for (const [field, read] of ANSWER_DIFF_FIELDS) {
      if (new Set(answers.map(read)).size > 1) out.add(field);
    }
    return out;
  }, [compare, caseId, picked, live, latest, interview]);

  // Compare mode: scrolling one card scrolls the others to the same relative position.
  const syncing = useRef(false);
  const onCardScroll = (e: UIEvent<HTMLDivElement>) => {
    const src = e.target as HTMLElement;
    if (!compare || syncing.current || !src.classList.contains("ccard")) return;
    syncing.current = true;
    const ratio = src.scrollTop / Math.max(1, src.scrollHeight - src.clientHeight);
    for (const el of scrollRef.current?.querySelectorAll<HTMLElement>(".ccard") ?? []) {
      if (el !== src) el.scrollTop = ratio * (el.scrollHeight - el.clientHeight);
    }
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  const togglePick = (id: ConditionId) =>
    setPicked((p) => (p.includes(id) ? (p.length > 2 ? p.filter((x) => x !== id) : p) : p.length < 3 ? [...p, id] : [...p.slice(1), id]));

  const shown = compare
    ? CONDITIONS.filter((c) => picked.includes(c.id))
    : tabs
      ? CONDITIONS.filter((c) => c.id === active)
      : CONDITIONS;

  return (
    <section className="pane" aria-labelledby="pane-conditions" data-coach="deck">
      <div className="pane-header deck-header">
        <h2 className="pane-title" id="pane-conditions">
          Conditions
        </h2>
        <div className="deck-tabs" role="group" aria-label={compare ? "Choose 2–3 conditions to compare" : "Jump to condition"}>
          {CONDITIONS.map((c, i) => {
            const entry = caseId ? live[resultKey(caseId, c.id, interview)] : undefined;
            const res = caseId ? latest?.[caseId]?.[c.id] : undefined;
            const st = entry?.status ?? (res ? (res.verdict.dangerous ? "danger" : res.status) : "idle");
            return (
              <button
                key={c.id}
                type="button"
                className="deck-tab mono"
                data-cond={c.id}
                aria-pressed={compare ? picked.includes(c.id) : tabs ? active === c.id : undefined}
                onClick={() => (compare ? togglePick(c.id) : scrollTo(c.id))}
                title={`${c.id} ${c.name} (key ${i + 1})`}
              >
                <span className="led" data-state={st} aria-hidden="true" />
                {c.id}
              </button>
            );
          })}
          <button type="button" className="chip deck-compare" aria-pressed={compare} onClick={() => setCompare(!compare)}>
            Compare
          </button>
        </div>
      </div>

      {caseId === null ? (
        <EmptySpecimen title="No specimen examined yet" testId="deck-empty">
          <p>
            Choose a case from the ledger, then press <kbd>R</kbd>. All five conditions — bare model, retrieval, tools,
            self-verify, guardrail — examine the same specimen, and each trace is recorded here as it happens.
          </p>
        </EmptySpecimen>
      ) : (
        <div
          ref={scrollRef}
          className="deck"
          data-mode={compare ? "compare" : tabs ? "tabs" : "scroll"}
          style={compare ? { gridTemplateColumns: `repeat(${shown.length}, minmax(0, 1fr))` } : undefined}
          onScrollCapture={onCardScroll}
        >
          {shown.map((c) => (
            <ConditionCard
              key={`${caseId}-${c.id}-${interview}`}
              condition={c}
              available={!interview || INTERVIEW_CONDITIONS.includes(c.id)}
              live={live[resultKey(caseId, c.id, interview)]}
              latest={latest?.[caseId]?.[c.id]}
              onCite={onCite}
              focused={!compare && active === c.id}
              diffs={compare ? diffs : undefined}
              caseData={caseData}
              dose={dose}
            />
          ))}
        </div>
      )}
    </section>
  );
}
