import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  QUESTION_TYPE_LABEL,
  SPECIES_CODES,
  SPECIES_CODE_LABEL,
  speciesCode,
  type Case,
  type QuestionType,
  type SpeciesCode,
} from "../../api/cases";
import { SpecimenTag, TypePill, UnverifiedTag } from "../../components/Tags";

const EASE = [0.2, 0.8, 0.2, 1] as const;
const TYPES = Object.keys(QUESTION_TYPE_LABEL) as QuestionType[];

export type DotState = "none" | "running" | "ok" | "error" | "danger";

const DOT_LABEL: Record<DotState, string> = {
  none: "not run",
  running: "running",
  ok: "last run: no dangerous errors",
  error: "last run: a condition failed",
  danger: "last run: at least one dangerous error",
};

interface Props {
  cases: Case[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  checked: Set<string>;
  onCheck: (ids: string[], on: boolean) => void;
  dots: Record<string, DotState>;
}

function matches(c: Case, q: string): boolean {
  if (!q) return true;
  const hay = [c.case_id, c.species, c.signalment.breed, c.owner_narrative, c.gold_answer.most_likely]
    .join(" ")
    .toLowerCase();
  return q
    .toLowerCase()
    .split(/\s+/)
    .every((term) => hay.includes(term));
}

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

export function CaseList({ cases, selectedId, onSelect, checked, onCheck, dots }: Props) {
  const [query, setQuery] = useState("");
  const [species, setSpecies] = useState<SpeciesCode | "ALL">("ALL");
  const [type, setType] = useState<QuestionType | "ALL">("ALL");
  const listRef = useRef<HTMLUListElement>(null);

  const visible = useMemo(
    () =>
      cases.filter(
        (c) =>
          (species === "ALL" || speciesCode(c.case_id) === species) &&
          (type === "ALL" || c.question_type === type) &&
          matches(c, query.trim()),
      ),
    [cases, species, type, query],
  );

  // The latest selection, readable before React re-renders (fast repeated J/K presses).
  const selRef = useRef(selectedId);
  useEffect(() => {
    selRef.current = selectedId;
  }, [selectedId]);

  // J / K move through the visible list; X toggles the batch checkbox.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      const key = e.key.toLowerCase();
      const current = selRef.current;
      if (key === "x" && current) {
        e.preventDefault();
        onCheck([current], !checked.has(current));
        return;
      }
      if (key !== "j" && key !== "k") return;
      if (visible.length === 0) return;
      e.preventDefault();
      const i = visible.findIndex((c) => c.case_id === current);
      const next = key === "j" ? Math.min(i + 1, visible.length - 1) : Math.max(i - 1, 0);
      const target = visible[i === -1 ? 0 : next];
      if (target) {
        selRef.current = target.case_id;
        onSelect(target.case_id);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [visible, onSelect, onCheck, checked]);

  useEffect(() => {
    if (!selectedId) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-case-id="${selectedId}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  const filtered = visible.length !== cases.length;

  return (
    <section className="pane" aria-labelledby="pane-cases">
      <div className="pane-header">
        <h2 className="pane-title" id="pane-cases">
          Cases
        </h2>
        <span className="pane-meta mono" aria-live="polite">
          {checked.size > 0 && (
            <button type="button" className="link-button" onClick={() => onCheck([...checked], false)}>
              clear {checked.size}
            </button>
          )}{" "}
          {filtered ? `${visible.length} / ${cases.length}` : cases.length}
        </span>
      </div>

      <div className="case-filters">
        <label className="visually-hidden" htmlFor="case-search">
          Search cases
        </label>
        <input
          id="case-search"
          className="case-search"
          type="search"
          placeholder="Search ID, breed, narrative…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoComplete="off"
        />
        <div className="chip-row" role="group" aria-label="Filter by species">
          <button type="button" className="chip" aria-pressed={species === "ALL"} onClick={() => setSpecies("ALL")}>
            All
          </button>
          {SPECIES_CODES.map((code) => (
            <button
              key={code}
              type="button"
              className="chip mono"
              data-species={code}
              aria-pressed={species === code}
              title={SPECIES_CODE_LABEL[code]}
              onClick={() => setSpecies(species === code ? "ALL" : code)}
            >
              {code}
            </button>
          ))}
        </div>
        <label className="visually-hidden" htmlFor="case-type">
          Filter by question type
        </label>
        <select
          id="case-type"
          className="case-select"
          value={type}
          onChange={(e) => setType(e.target.value as QuestionType | "ALL")}
        >
          <option value="ALL">All question types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {QUESTION_TYPE_LABEL[t]}
            </option>
          ))}
        </select>
      </div>

      {visible.length === 0 ? (
        <div className="empty">
          <p className="empty-title">No cases match</p>
          <button
            type="button"
            className="link-button"
            onClick={() => {
              setQuery("");
              setSpecies("ALL");
              setType("ALL");
            }}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <ul className="case-list" role="listbox" aria-label="Cases" ref={listRef}>
          {visible.map((c) => {
            const selected = c.case_id === selectedId;
            return (
              <li
                key={c.case_id}
                role="option"
                aria-selected={selected}
                tabIndex={selected || (!selectedId && c === visible[0]) ? 0 : -1}
                className="case-row"
                data-case-id={c.case_id}
                onClick={() => onSelect(c.case_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect(c.case_id);
                  }
                }}
              >
                {selected && (
                  <motion.span
                    layoutId="case-active"
                    className="case-row-active"
                    transition={{ duration: 0.2, ease: EASE }}
                  />
                )}
                <span className="case-row-line">
                  <span className="case-row-left">
                    <input
                      type="checkbox"
                      className="case-check"
                      tabIndex={-1}
                      checked={checked.has(c.case_id)}
                      aria-label={`Select ${c.case_id} for a batch run (X)`}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => onCheck([c.case_id], e.target.checked)}
                    />
                    <SpecimenTag caseId={c.case_id} />
                    <span
                      className="result-dot"
                      data-state={dots[c.case_id] ?? "none"}
                      title={DOT_LABEL[dots[c.case_id] ?? "none"]}
                      aria-label={DOT_LABEL[dots[c.case_id] ?? "none"]}
                      role="img"
                    />
                  </span>
                  <TypePill type={c.question_type} />
                </span>
                <span className="case-row-line case-row-meta">
                  <span className="case-row-species">{c.species}</span>
                  <span className="mono case-row-weight">{c.signalment.weight_kg} kg</span>
                  <span className="case-row-breed">{c.signalment.breed}</span>
                  {!c.vet_verified && <UnverifiedTag />}
                </span>
              </li>
            );
          })}
        </ul>
      )}
      <p className="pane-hint mono">J / K move · X select · R run</p>
    </section>
  );
}
