import { useEffect, useRef, useState } from "react";
import { INTERVIEW_CONDITIONS, resultKey, type ConditionId, type LatestResults } from "../../api/runs";
import { useRun } from "../../app/runState";
import { CONDITIONS } from "../../app/conditions";
import { ConditionCard } from "./ConditionCard";

interface Props {
  caseId: string | null;
  interview: boolean;
  latest: LatestResults | undefined;
  onCite: (page: number) => void;
  /** Narrow screens: show one condition at a time, chosen by the tabs. */
  tabs?: boolean;
}

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function ConditionDeck({ caseId, interview, latest, onCite, tabs = false }: Props) {
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

  const togglePick = (id: ConditionId) =>
    setPicked((p) => (p.includes(id) ? (p.length > 2 ? p.filter((x) => x !== id) : p) : p.length < 3 ? [...p, id] : [...p.slice(1), id]));

  const shown = compare
    ? CONDITIONS.filter((c) => picked.includes(c.id))
    : tabs
      ? CONDITIONS.filter((c) => c.id === active)
      : CONDITIONS;

  return (
    <section className="pane" aria-labelledby="pane-conditions">
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
                <span className="deck-dot" data-state={st} aria-hidden="true" />
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
        <div className="empty">
          <p className="empty-title serif empty-title-lg">Nothing to compare yet</p>
          <p className="empty-body">
            Select a case, then press R. Each condition — bare model, retrieval, tools, self-verify, guardrail — answers the
            same question, and its trace streams in here step by step.
          </p>
        </div>
      ) : (
        <div
          ref={scrollRef}
          className="deck"
          data-mode={compare ? "compare" : tabs ? "tabs" : "scroll"}
          style={compare ? { gridTemplateColumns: `repeat(${shown.length}, minmax(0, 1fr))` } : undefined}
        >
          {shown.map((c) => (
            <ConditionCard
              key={`${caseId}-${c.id}-${interview}`}
              condition={c}
              available={!interview || INTERVIEW_CONDITIONS.includes(c.id)}
              live={live[resultKey(caseId, c.id, interview)]}
              latest={latest?.[caseId]?.[c.id]}
              onCite={onCite}
            />
          ))}
        </div>
      )}
    </section>
  );
}
