import { motion } from "motion/react";
import { Group, Panel, Separator } from "react-resizable-panels";
import { useHealth } from "../../api/health";
import { CONDITIONS, LADDER_STEPS } from "../../app/conditions";
import { AblationLadder } from "../../components/AblationLadder";
import { GraphPaper } from "../../components/GraphPaper";
import "./bench.css";

const EASE = [0.2, 0.8, 0.2, 1] as const;

function PaneHeader({ id, title, meta }: { id: string; title: string; meta?: string | undefined }) {
  return (
    <div className="pane-header">
      <h2 className="pane-title" id={id}>{title}</h2>
      {meta && <span className="pane-meta mono">{meta}</span>}
    </div>
  );
}

/** Outline of a specimen tag — the empty slot a case will occupy. */
function EmptyTag() {
  return (
    <div className="empty-tag" aria-hidden="true">
      <span className="empty-tag-hole" />
      <span className="empty-tag-id mono">———————</span>
    </div>
  );
}

function CaseListPane() {
  const { data, error, isPending } = useHealth();
  const count = data?.counts.cases ?? 0;
  let body: string;
  if (isPending) body = "Checking data files…";
  else if (error) body = `Cannot reach the backend: ${error.message}`;
  else if (count === 0) body = "data/cases.json is not present yet. The case set is built in Milestone 2.";
  else body = `${count} cases on disk. The case list view is built in Milestone 2.`;

  return (
    <section className="pane" aria-labelledby="pane-cases">
      <PaneHeader id="pane-cases" title="Cases" meta={data ? String(count) : undefined} />
      <div className="empty">
        <EmptyTag />
        <p className="empty-title">
          No cases loaded
        </p>
        <p className="empty-body">{body}</p>
      </div>
    </section>
  );
}

function CasePane() {
  return (
    <section className="pane pane-case" aria-labelledby="pane-case">
      <PaneHeader id="pane-case" title="Case" />
      <div className="empty">
        <p className="empty-title serif empty-title-lg">
          No case selected
        </p>
        <p className="empty-body">
          A selected case shows its signalment, history, owner narrative, clinical signs and red flags here.
          The gold answer stays hidden until you reveal it.
        </p>
      </div>
    </section>
  );
}

function ConditionsPane() {
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
            <p className="condition-status mono">Waiting for a case</p>
          </motion.li>
        ))}
      </motion.ul>
    </section>
  );
}

export function BenchPage() {
  return (
    <div className="bench" data-testid="bench">
      <GraphPaper />
      <Group orientation="horizontal" id="bench-panes" className="bench-panes">
        <Panel id="cases" defaultSize="24" minSize="200px">
          <CaseListPane />
        </Panel>
        <Separator className="pane-separator" />
        <Panel id="case" defaultSize="38" minSize="280px">
          <CasePane />
        </Panel>
        <Separator className="pane-separator" />
        <Panel id="conditions" defaultSize="38" minSize="300px">
          <ConditionsPane />
        </Panel>
      </Group>
    </div>
  );
}
