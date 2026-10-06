import { motion } from "motion/react";
import { useCallback, useMemo, useState, type CSSProperties } from "react";
import { useSearchParams } from "react-router";
import type { ConditionId } from "../../api/runs";
import { fmtP, pct, useRuns, useScorecard, type BreakdownRow, type Rate, type Scorecard } from "../../api/scorecard";
import { CONDITIONS } from "../../app/conditions";
import { Switchboard } from "../../components/Switchboard";
import { RollingNumber } from "../../components/RollingNumber";
import { DotWhisker } from "./DotWhisker";
import "./scorecard.css";
import { PageTitle } from "../../components/PageHeader";
import { SectionTitle } from "../../components/Ink";

const EASE = [0.2, 0.8, 0.2, 1] as const;
const COND = Object.fromEntries(CONDITIONS.map((c) => [c.id, c])) as Record<ConditionId, (typeof CONDITIONS)[number]>;
const fmtPct = (v: number) => `${Math.round(v * 100)}%`;
const fmtInt = (v: number) => Math.round(v).toLocaleString("en-IN");

function RateCell({ r }: { r: Rate | undefined }) {
  if (!r || r.rate === null) return <span className="sc-na">n/a</span>;
  return (
    <>
      <span className="sc-rate">{pct(r.rate, 1)}</span>{" "}
      <span className="sc-ci">
        [{pct(r.lo, 0)}–{pct(r.hi, 0)}] {r.k}/{r.n}
      </span>
    </>
  );
}

function Tile({ label, a, b, condA, condB, format, note }: {
  label: string; a: number | null; b: number | null; condA: string; condB: string; format: (v: number) => string; note?: string;
}) {
  return (
    <div className="sc-tile">
      <span className="eyebrow">{label}</span>
      <div className="sc-tile-nums">
        <span className="sc-tile-pair">
          <span className="sc-tile-cond mono">{condA}</span>
          <span className="sc-big serif">{a === null ? "—" : <RollingNumber text={format(a)} />}</span>
        </span>
        {condB && (
          <>
            <span className="sc-arrow" aria-hidden="true">→</span>
            <span className="sc-tile-pair">
              <span className="sc-tile-cond mono">{condB}</span>
              <span className="sc-big serif">{b === null ? "—" : <RollingNumber text={format(b)} />}</span>
            </span>
          </>
        )}
      </div>
      {note && <span className="sc-tile-note">{note}</span>}
    </div>
  );
}

function Breakdown({ title, rows, conditions }: { title: string; rows: BreakdownRow[]; conditions: ConditionId[] }) {
  return (
    <section className="sc-section">
      <SectionTitle>{title}</SectionTitle>
      <div className="sc-table-wrap">
        <table className="sc-table ledger">
          <thead>
            <tr>
              <th scope="col">Group</th>
              <th scope="col" className="num">n</th>
              {conditions.map((c) => (
                <th key={c} scope="col" data-cond={c}>
                  <span className="sc-th-cond mono">{c}</span>
                  <span className="sc-th-sub">top-1 · danger</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.group}>
                <th scope="row">{row.label}</th>
                <td className="num mono">{row.n_cases}</td>
                {conditions.map((c) => {
                  const v = row.by_condition[c];
                  return (
                    <td key={c} className="mono">
                      {v ? (
                        <>
                          {pct(v.dx_top1.rate)} · <span data-bad={(v.dangerous.rate ?? 0) > 0}>{pct(v.dangerous.rate)}</span>
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Hero figure: 72px Instrument Serif, misregistered, counting up via the registered --count property. */
function HeroNumber({ value }: { value: number | null }) {
  if (value === null) return <span className="sc-hero-num serif">—</span>;
  const n = Math.round(value * 100);
  return (
    <span className="sc-hero-num serif misreg">
      <span className="visually-hidden">{n}%</span>
      <span className="count" aria-hidden="true" style={{ "--to": n, "--suffix": '"%"' } as CSSProperties} />
    </span>
  );
}

/** The three headline numbers for the best condition against C0: false-safe, under-triage, top-3.
 *  "Best" = fewest dangerous errors, then highest top-3 accuracy. */
function Hero({ sc }: { sc: Scorecard }) {
  const rate = (key: string, c: ConditionId) => sc.metrics.find((m) => m.key === key)?.by_condition[c]?.rate ?? null;
  const base = sc.conditions[0] as ConditionId;
  const others = sc.conditions.slice(1);
  if (others.length === 0) return null;
  const best = [...others].sort(
    (a, b) => (rate("dangerous", a) ?? 1) - (rate("dangerous", b) ?? 1) || (rate("dx_top3", b) ?? 0) - (rate("dx_top3", a) ?? 0),
  )[0] as ConditionId;
  const items = [
    { key: "false_safe", label: "False-safe drug rate", better: "lower" },
    { key: "under_triage", label: "Under-triage rate", better: "lower" },
    { key: "dx_top3", label: "Top-3 diagnosis", better: "higher" },
  ] as const;
  return (
    <section className="sc-hero" aria-label={`Headline: ${best} against ${base}`} data-testid="sc-hero">
      <div className="sc-hero-kicker">
        <span className="mono" data-cond={best}>{best}</span> {COND[best].name}
        <Switchboard condition={COND[best]} />
        <span className="sc-hero-vs">against</span>
        <span className="mono" data-cond={base}>{base}</span> {COND[base].name}
      </div>
      <div className="sc-hero-grid">
        {items.map((it) => {
          const a = rate(it.key, best);
          const b = rate(it.key, base);
          const delta = a !== null && b !== null ? Math.round((a - b) * 100) : null;
          const good = delta !== null && (it.better === "lower" ? delta < 0 : delta > 0);
          return (
            <div key={it.key} className="sc-hero-item">
              <span className="eyebrow">{it.label}</span>
              <HeroNumber value={a} />
              <span className="sc-hero-base mono">
                {base} {b === null ? "n/a" : `${Math.round(b * 100)}%`}
                {delta !== null && delta !== 0 && (
                  <span className="sc-hero-delta" data-good={good}>
                    {" "}
                    {delta > 0 ? "+" : "−"}
                    {Math.abs(delta)} pts
                  </span>
                )}
              </span>
              <span className="sc-hero-note">{it.better} is better</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Report({ sc }: { sc: Scorecard }) {
  const conds = sc.conditions;
  const first = conds[0] as ConditionId;
  const last = conds[conds.length - 1] as ConditionId;
  const metric = (key: string) => sc.metrics.find((m) => m.key === key);
  const rateOf = (key: string, c: ConditionId) => metric(key)?.by_condition[c]?.rate ?? null;
  const totalTokens = conds.reduce((s, c) => s + (sc.usage[c]?.total_tokens ?? 0), 0);
  const costs = conds.map((c) => sc.usage[c]?.total_cost_usd ?? null);
  const totalCost = costs.some((c) => c === null) ? null : costs.reduce<number>((s, c) => s + (c ?? 0), 0);
  const pairs = conds.slice(1).map((b, i) => [conds[i] as ConditionId, b] as const);
  const isDemo = sc.run.provider === "demo";

  return (
    <>
      {sc.warnings.length > 0 && (
        <div className="sc-warnings" role="note" data-demo={isDemo}>
          {sc.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </div>
      )}

      <div className="sc-report-head print-only">
        <span className="sc-report-title">VetAgentBench-IN · Lab report</span>
        <span className="sc-report-meta">
          Run {sc.run.id} · {sc.run.provider}/{sc.run.model} · {sc.n_cases} cases × {conds.length} conditions
        </span>
      </div>

      <Hero sc={sc} />

      <motion.div
        className="sc-tiles"
        initial="hidden"
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.05 } } }}
      >
        {[
          <Tile key="n" label="Cases scored" a={sc.n_cases} b={null} condA="" condB="" format={fmtInt} note={`${conds.length} conditions · ${sc.run.provider}/${sc.run.model}`} />,
          <Tile key="top1" label="Top-1 diagnosis" a={rateOf("dx_top1", first)} b={rateOf("dx_top1", last)} condA={first} condB={last} format={fmtPct} />,
          <Tile key="danger" label="Any dangerous error" a={rateOf("dangerous", first)} b={rateOf("dangerous", last)} condA={first} condB={last} format={fmtPct} note="lower is better" />,
          <Tile key="esc" label="Missed escalation" a={rateOf("missed_escalation", first)} b={rateOf("missed_escalation", last)} condA={first} condB={last} format={fmtPct} note="lower is better" />,
          <Tile key="tok" label="Tokens" a={totalTokens} b={null} condA="" condB="" format={fmtInt} note={totalCost === null ? "cost unknown — set prices in .env" : `cost $${totalCost.toFixed(4)}`} />,
        ].map((t, i) => (
          <motion.div key={i} variants={{ hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE } } }}>
            {t}
          </motion.div>
        ))}
      </motion.div>

      <section className="sc-section">
        <div className="sc-section-head">
          <SectionTitle>Rates with 95% Wilson intervals</SectionTitle>
          <div className="sc-legend" aria-label="Conditions">
            {conds.map((c) => (
              <span key={c} className="sc-legend-item" data-cond={c}>
                <span className="dw-swatch" aria-hidden="true" />
                <span className="mono">{c}</span> {COND[c].name}
                <Switchboard condition={COND[c]} />
              </span>
            ))}
          </div>
        </div>
        <div className="sc-charts">
          {sc.metrics.map((m) => (
            <DotWhisker key={m.key} metric={m} conditions={conds} />
          ))}
        </div>
      </section>

      <section className="sc-section">
        <SectionTitle>Metrics table</SectionTitle>
        <div className="sc-table-wrap">
          <table className="sc-table ledger" data-testid="metrics-table">
            <thead>
              <tr>
                <th scope="col">Metric</th>
                {conds.map((c) => (
                  <th key={c} scope="col" data-cond={c}>
                    <span className="sc-th-cond mono">{c}</span>
                    <span className="sc-th-sub">{COND[c].name}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sc.metrics.map((m) => (
                <tr key={m.key}>
                  <th scope="row" title={m.description}>
                    {m.label} <span className="sc-dir mono">{m.better === "higher" ? "↑" : "↓"}</span>
                  </th>
                  {conds.map((c) => (
                    <td key={c} className="mono">
                      <RateCell r={m.by_condition[c]} />
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="sc-usage-row">
                <th scope="row">Avg tool steps</th>
                {conds.map((c) => (
                  <td key={c} className="mono">{sc.usage[c]?.avg_steps?.toFixed(1) ?? "—"}</td>
                ))}
              </tr>
              <tr className="sc-usage-row">
                <th scope="row">Avg tokens</th>
                {conds.map((c) => (
                  <td key={c} className="mono">{sc.usage[c]?.avg_tokens ? fmtInt(sc.usage[c]?.avg_tokens ?? 0) : "—"}</td>
                ))}
              </tr>
              <tr className="sc-usage-row">
                <th scope="row">Cost (USD)</th>
                {conds.map((c) => {
                  const v = sc.usage[c]?.total_cost_usd;
                  return (
                    <td key={c} className="mono">{v === null || v === undefined ? "unknown" : v.toFixed(4)}</td>
                  );
                })}
              </tr>
              <tr className="sc-usage-row">
                <th scope="row">Failed results</th>
                {conds.map((c) => (
                  <td key={c} className="mono" data-bad={(sc.usage[c]?.errors ?? 0) > 0}>{sc.usage[c]?.errors ?? 0}</td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {pairs.length > 0 && (
        <section className="sc-section">
          <SectionTitle>McNemar tests, adjacent conditions</SectionTitle>
          <p className="sc-note">
            Exact two-sided test on paired cases. Cells show p and the discordant counts (only first · only second
            succeeded). For “lower is better” metrics a “success” is the error occurring.
          </p>
          <div className="sc-table-wrap">
            <table className="sc-table ledger" data-testid="mcnemar-table">
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  {pairs.map(([a, b]) => (
                    <th key={a + b} scope="col" className="mono">{a} → {b}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sc.metrics.map((m) => (
                  <tr key={m.key}>
                    <th scope="row">{m.label}</th>
                    {pairs.map(([a, b]) => {
                      const t = sc.mcnemar.find((x) => x.metric === m.key && x.a === a && x.b === b);
                      return (
                        <td key={a + b} className="mono" data-sig={t?.p !== null && t?.p !== undefined && t.p < 0.05}>
                          {t ? (
                            <>
                              p {fmtP(t.p)} <span className="sc-ci">({t.only_a}·{t.only_b}, n={t.n_pairs})</span>
                            </>
                          ) : (
                            "—"
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div className="sc-two sc-breakdowns">
        <Breakdown title="By species" rows={sc.breakdowns.species} conditions={conds} />
        <Breakdown title="By question type" rows={sc.breakdowns.question_type} conditions={conds} />
      </div>

      <p className="sc-report-foot print-only">
        Research prototype — not for clinical use. Gold answers unverified by a veterinarian. Rates with 95% Wilson
        intervals; exact McNemar tests between adjacent conditions.
      </p>
    </>
  );
}

export function ScorecardPage() {
  const [params, setParams] = useSearchParams();
  const [runId, setRunIdState] = useState<string | null>(() => params.get("run"));
  const { data: runs } = useRuns();
  const { data: sc, error, isPending } = useScorecard(runId);

  const setRunId = useCallback(
    (id: string | null) => {
      setRunIdState(id);
      setParams((p) => {
        const n = new URLSearchParams(p);
        if (id) n.set("run", id);
        else n.delete("run");
        return n;
      }, { replace: true });
    },
    [setParams],
  );

  const effective = sc?.run.id ?? runId;
  const runOptions = useMemo(() => (runs ?? []).filter((r) => r.n_done > 0), [runs]);
  const q = effective ? `?run_id=${encodeURIComponent(effective)}` : "";

  return (
    <div className="scorecard" data-testid="scorecard">
      <header className="sc-header">
        <div>
          <PageTitle plate="06" className="sc-title">Scorecard</PageTitle>
          <p className="sc-sub">
            Accuracy and dangerous errors per condition, with 95% Wilson intervals and McNemar tests between adjacent
            conditions.
          </p>
        </div>
        <div className="sc-controls">
          <label className="sc-run-label eyebrow" htmlFor="run-select">
            Run
          </label>
          <select
            id="run-select"
            className="case-select sc-run-select"
            value={effective ?? ""}
            onChange={(e) => setRunId(e.target.value || null)}
          >
            {!effective && <option value="">Latest</option>}
            {runOptions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.created_at.replace("T", " ").slice(0, 16)} · {r.provider} · {r.case_ids.length} case{r.case_ids.length > 1 ? "s" : ""} × {r.conditions.length}
                {r.interview ? " · interview" : ""} · {r.status}
              </option>
            ))}
          </select>
          <a className="btn" href={`/api/scorecard/export.csv${q}`} download data-testid="export-csv">
            CSV
          </a>
          <a className="btn" href={`/api/scorecard/export.json${q}`} download>
            JSON
          </a>
          <button type="button" className="btn" onClick={() => window.print()}>
            Print
          </button>
        </div>
      </header>

      {isPending && <p className="empty-body">Scoring…</p>}
      {error && (
        <div className="empty">
          <p className="empty-title serif empty-title-lg">No scorecard yet</p>
          <p className="empty-body error-text" role="alert">
            {error.message}
          </p>
        </div>
      )}
      {sc && <Report sc={sc} />}
    </div>
  );
}
