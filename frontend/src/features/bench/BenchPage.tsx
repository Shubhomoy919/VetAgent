import { useCallback, useEffect, useMemo, useState } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { useSearchParams } from "react-router";
import { useCases, type Case } from "../../api/cases";
import { CONDITION_IDS, resultKey, useLatestResults } from "../../api/runs";
import { useRun } from "../../app/runState";
import { NARROW, WIDE, useMediaQuery } from "../../app/useMediaQuery";
import { withViewTransition } from "../../lib/viewTransition";
import { CaseDetail } from "./CaseDetail";
import { CaseDossier } from "./CaseDossier";
import { CaseList, type DotState } from "./CaseList";
import { ConditionDeck } from "./ConditionDeck";
import { PassageDrawer } from "./PassageDrawer";
import { RunBar } from "./RunBar";
import "./bench.css";
import "./run.css";

/** Outline of a specimen tag — the empty slot a case will occupy. */
function EmptyTag() {
  return (
    <div className="empty-tag" aria-hidden="true">
      <span className="empty-tag-hole" />
      <span className="empty-tag-id mono">———————</span>
    </div>
  );
}

function isTypingTarget(el: EventTarget | null): boolean {
  return el instanceof HTMLElement && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

function CasePane({ selected, onOpenDossier }: { selected: Case | undefined; onOpenDossier: () => void }) {
  return (
    <section className="pane pane-case" aria-labelledby="pane-case">
      <div className="pane-header">
        <h2 className="pane-title" id="pane-case">
          Case
        </h2>
      </div>
      {selected ? (
        <div className="pane-scroll">
          <CaseDetail key={selected.case_id} c={selected} onOpenDossier={onOpenDossier} />
        </div>
      ) : (
        <div className="empty">
          <p className="empty-title serif empty-title-lg">No case selected</p>
          <p className="empty-body">
            Pick a case from the list (or press J) to see its signalment, history, owner narrative, clinical signs and
            red flags. The gold answer stays hidden until you reveal it.
          </p>
        </div>
      )}
    </section>
  );
}

export function BenchPage() {
  const [params, setParams] = useSearchParams();
  // Local state is the source of truth (updates synchronously); the URL mirrors it for deep links.
  const [selectedId, setSelectedId] = useState<string | null>(() => params.get("case"));
  const [interview, setInterviewState] = useState(() => params.get("mode") === "interview");
  const [force, setForce] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [citePage, setCitePage] = useState<number | null>(null);
  const [casesOpen, setCasesOpen] = useState(false);
  const [dossierOpen, setDossierOpen] = useState(false);
  const openDossier = useCallback(() => setDossierOpen(true), []);
  const closeDossier = useCallback(() => setDossierOpen(false), []);
  const wide = useMediaQuery(WIDE);
  const narrow = useMediaQuery(NARROW);

  const { data: cases, error, isPending } = useCases();
  const { data: latest } = useLatestResults(interview);
  const { live, run, start, starting } = useRun();
  const selected = cases?.find((c) => c.case_id === selectedId);

  // Ground watermark: the case under examination.
  useEffect(() => {
    document.body.dataset.watermark = selectedId ?? "Bench";
  }, [selectedId]);

  const setParam = useCallback(
    (key: string, value: string | null) =>
      setParams(
        (p) => {
          const next = new URLSearchParams(p);
          if (value === null) next.delete(key);
          else next.set(key, value);
          return next;
        },
        { replace: true },
      ),
    [setParams],
  );
  const onSelect = useCallback(
    (id: string) => {
      setSelectedId(id);
      setParam("case", id);
    },
    [setParam],
  );
  const onSelectFromList = useCallback(
    (id: string) => {
      // Case switching slides the case pane through a view transition (plain update if unsupported).
      withViewTransition("case", () => onSelect(id));
      if (!wide) setCasesOpen(false);
    },
    [onSelect, wide],
  );
  const setInterview = useCallback(
    (v: boolean) => {
      setInterviewState(v);
      setParam("mode", v ? "interview" : null);
    },
    [setParam],
  );

  const onCheck = useCallback((ids: string[], on: boolean) => {
    setChecked((prev) => {
      const next = new Set(prev);
      for (const id of ids) {
        if (on) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  }, []);

  const dots = useMemo(() => {
    const out: Record<string, DotState> = {};
    for (const c of cases ?? []) {
      const keys = CONDITION_IDS.map((cond) => live[resultKey(c.case_id, cond, interview)]);
      if (keys.some((k) => k?.status === "running" || k?.status === "queued")) {
        out[c.case_id] = "running";
        continue;
      }
      const results = Object.values(latest?.[c.case_id] ?? {});
      if (results.length === 0) out[c.case_id] = "none";
      else if (results.some((r) => r?.verdict.dangerous)) out[c.case_id] = "danger";
      else if (results.some((r) => r?.status === "error")) out[c.case_id] = "error";
      else out[c.case_id] = "ok";
    }
    return out;
  }, [cases, latest, live, interview]);

  // R = run this case, Shift+R = force re-run this case.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isTypingTarget(e.target)) return;
      if (e.key.toLowerCase() !== "r" || !selectedId) return;
      if (run?.status === "running" || starting) return;
      e.preventDefault();
      void start({ case_ids: [selectedId], interview, force: e.shiftKey || force });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId, interview, force, run?.status, starting, start]);

  const closeDrawer = useCallback(() => setCitePage(null), []);

  // Escape closes the case drawer (medium and narrow layouts).
  useEffect(() => {
    if (!casesOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCasesOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [casesOpen]);

  const caseListPane = cases ? (
    <CaseList cases={cases} selectedId={selectedId} onSelect={onSelectFromList} checked={checked} onCheck={onCheck} dots={dots} />
  ) : (
    <section className="pane" aria-labelledby="pane-cases">
      <div className="pane-header">
        <h2 className="pane-title" id="pane-cases">
          Cases
        </h2>
      </div>
      <div className="empty">
        <EmptyTag />
        <p className="empty-title">{isPending ? "Loading cases…" : "Cases could not be loaded"}</p>
        {error && (
          <p className="empty-body error-text" role="alert">
            {error.message}
          </p>
        )}
      </div>
    </section>
  );
  const deck = (
    <ConditionDeck caseId={selected ? selected.case_id : null} interview={interview} latest={latest} onCite={setCitePage} tabs={narrow} />
  );
  const allIds = useMemo(() => (cases ?? []).map((c) => c.case_id), [cases]);

  return (
    <div className="bench" data-testid="bench">
      <RunBar
        caseId={selectedId}
        selected={[...checked]}
        allIds={allIds}
        interview={interview}
        force={force}
        setInterview={setInterview}
        setForce={setForce}
        onOpenCases={wide ? undefined : () => setCasesOpen(true)}
      />
      {wide ? (
        <Group key="wide" orientation="horizontal" id="bench-panes" className="bench-panes">
          <Panel id="cases" defaultSize="25" minSize="280px">
            {caseListPane}
          </Panel>
          <Separator className="pane-separator" />
          <Panel id="case" defaultSize="31" minSize="300px">
            <CasePane selected={selected} onOpenDossier={openDossier} />
          </Panel>
          <Separator className="pane-separator" />
          <Panel id="conditions" defaultSize="44" minSize="320px">
            {deck}
          </Panel>
        </Group>
      ) : (
        <>
          <div className={`cases-drawer-scrim${casesOpen ? " open" : ""}`} onClick={() => setCasesOpen(false)} aria-hidden="true" />
          <div className="cases-drawer" data-open={casesOpen} inert={!casesOpen} data-testid="cases-drawer">
            {caseListPane}
          </div>
          <Group
            key={narrow ? "narrow" : "medium"}
            orientation={narrow ? "vertical" : "horizontal"}
            id={narrow ? "bench-panes-narrow" : "bench-panes-medium"}
            className="bench-panes"
          >
            <Panel id="case" defaultSize={narrow ? "42" : "42"} minSize={narrow ? "160px" : "300px"}>
              <CasePane selected={selected} onOpenDossier={openDossier} />
            </Panel>
            <Separator className={narrow ? "pane-separator pane-separator-h" : "pane-separator"} />
            <Panel id="conditions" defaultSize="58" minSize={narrow ? "200px" : "320px"}>
              {deck}
            </Panel>
          </Group>
        </>
      )}
      <CaseDossier c={dossierOpen && selected ? selected : null} onClose={closeDossier} onCite={setCitePage} />
      <PassageDrawer page={citePage} onClose={closeDrawer} />
    </div>
  );
}
