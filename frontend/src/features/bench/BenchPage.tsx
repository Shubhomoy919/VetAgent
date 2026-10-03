import { motion } from "motion/react";
import { useCallback } from "react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { useSearchParams } from "react-router";
import { useCases, type Case } from "../../api/cases";
import { CONDITIONS, LADDER_STEPS } from "../../app/conditions";
import { AblationLadder } from "../../components/AblationLadder";
import { GraphPaper } from "../../components/GraphPaper";
import { CaseDetail } from "./CaseDetail";
import { CaseList } from "./CaseList";
import "./bench.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

/** Outline of a specimen tag — the empty slot a case will occupy. */
function EmptyTag() {
  return (
    <div className="empty-tag" aria-hidden="true">
      <span className="empty-tag-hole" />
      <span className="empty-tag-id mono">———————</span>
    </div>
  );
}

function CaseListPane({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { data, error, isPending } = useCases();
  if (data) return <CaseList cases={data} selectedId={selectedId} onSelect={onSelect} />;
  return (
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
}

function CasePane({ selected }: { selected: Case | undefined }) {
  return (
    <section className="pane pane-case" aria-labelledby="pane-case">
      <div className="pane-header">
        <h2 className="pane-title" id="pane-case">
          Case
        </h2>
      </div>
      {selected ? (
        <div className="pane-scroll">
          <CaseDetail key={selected.case_id} c={selected} />
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

function ConditionsPane({ hasCase }: { hasCase: boolean }) {
  return (
    <section className="pane" aria-labelledby="pane-conditions">
      <div className="pane-header">
        <h2 className="pane-title" id="pane-conditions">
          Conditions
        </h2>
        <ol className="ladder-legend mono" aria-label="Ablation ladder components">
          {LADDER_STEPS.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
      </div>
      <motion.ul
        className="conditions"
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.04 } } }}
      >
        {CONDITIONS.map((c) => (
          <motion.li
            key={c.id}
            className="condition"
            data-cond={c.id}
            variants={{
              hidden: { opacity: 0, y: 6 },
              show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE } },
            }}
          >
            <span className="condition-bar" aria-hidden="true" />
            <div className="condition-head">
              <span className="condition-id mono">{c.id}</span>
              <span className="condition-name">{c.name}</span>
              <AblationLadder condition={c} />
            </div>
            <p className="condition-summary">{c.summary}</p>
            <p className="condition-status mono">{hasCase ? "Not run" : "Waiting for a case"}</p>
          </motion.li>
        ))}
      </motion.ul>
    </section>
  );
}

export function BenchPage() {
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("case");
  const { data: cases } = useCases();
  const selected = cases?.find((c) => c.case_id === selectedId);

  const onSelect = useCallback(
    (id: string) => setParams((p) => {
      const next = new URLSearchParams(p);
      next.set("case", id);
      return next;
    }, { replace: true }),
    [setParams],
  );

  return (
    <div className="bench" data-testid="bench">
      <GraphPaper />
      <Group orientation="horizontal" id="bench-panes" className="bench-panes">
        <Panel id="cases" defaultSize="26" minSize="260px">
          <CaseListPane selectedId={selectedId} onSelect={onSelect} />
        </Panel>
        <Separator className="pane-separator" />
        <Panel id="case" defaultSize="40" minSize="320px">
          <CasePane selected={selected} />
        </Panel>
        <Separator className="pane-separator" />
        <Panel id="conditions" defaultSize="34" minSize="300px">
          <ConditionsPane hasCase={Boolean(selected)} />
        </Panel>
      </Group>
    </div>
  );
}
