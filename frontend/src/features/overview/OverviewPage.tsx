import { Link } from "react-router";
import { useHealth } from "../../api/health";
import { useRunList } from "../../api/admin";
import { pct, useScorecard } from "../../api/scorecard";
import type { ConditionId } from "../../api/runs";
import { CONDITIONS } from "../../app/conditions";
import { AblationLadder } from "../../components/AblationLadder";
import { DotWhisker } from "../scorecard/DotWhisker";
import "../data/data.css";
import "../scorecard/scorecard.css";
import "./overview.css";
import { PageTitle } from "../../components/PageHeader";

export function OverviewPage() {
  const { data: health } = useHealth();
  const { data: sc, error: scError } = useScorecard(null);
  const { data: runs } = useRunList();

  const conds = sc?.conditions ?? [];
  const first = conds[0] as ConditionId | undefined;
  const last = conds[conds.length - 1] as ConditionId | undefined;
  const m = (key: string) => sc?.metrics.find((x) => x.key === key);
  const rate = (key: string, c: ConditionId | undefined) => (c ? m(key)?.by_condition[c]?.rate ?? null : null);
  const danger = m("dangerous");

  return (
    <div className="datapage overview" data-testid="overview-page">
      <header className="dp-header">
        <div>
          <PageTitle plate="08">VetAgentBench-IN</PageTitle>
          <p className="dp-sub ov-lede">
            Does giving a language model retrieval, tools, self-verification and hard safety rules make its veterinary
            advice safer? The same India-focused cases run through five conditions; we count accuracy and, above all,
            dangerous errors.
          </p>
        </div>
        <button type="button" className="btn" onClick={() => window.print()}>
          Print
        </button>
      </header>

      <section className="ov-strip" aria-label="Status">
        <div className="ov-stat">
          <span className="eyebrow">Mode</span>
          <span className="ov-val mono" data-mode={health?.mode}>{health ? (health.mode === "live" ? `live · ${health.model}` : "demo") : "—"}</span>
        </div>
        <div className="ov-stat">
          <span className="eyebrow">Cases</span>
          <span className="ov-val serif">{health?.counts.cases ?? "—"}</span>
        </div>
        <div className="ov-stat">
          <span className="eyebrow">Drug rows</span>
          <span className="ov-val serif">{health?.counts.drugs ?? "—"}</span>
        </div>
        <div className="ov-stat">
          <span className="eyebrow">SVTG</span>
          <span className="ov-val mono">{health ? `${health.pages} pp · ${health.chunks} chunks` : "—"}</span>
        </div>
        <div className="ov-stat">
          <span className="eyebrow">Runs</span>
          <span className="ov-val serif">{health?.counts.runs ?? "—"}</span>
        </div>
      </section>

      <section className="ov-section">
        <h2 className="sc-h2">Five conditions, one answer schema</h2>
        <div className="ov-conds">
          {CONDITIONS.map((c) => (
            <div key={c.id} className="ov-cond" data-cond={c.id}>
              <div className="ov-cond-head">
                <span className="mono">{c.id}</span> <strong>{c.name}</strong>
              </div>
              <AblationLadder condition={c} />
            </div>
          ))}
        </div>
      </section>

      <section className="ov-section">
        <div className="sc-section-head">
          <h2 className="sc-h2">Latest results</h2>
          {sc && (
            <Link className="link-button" to={`/scorecard?run=${encodeURIComponent(sc.run.id)}`}>
              Full scorecard
            </Link>
          )}
        </div>
        {scError && <p className="empty-body">{scError.message}</p>}
        {sc && (
          <>
            {sc.warnings.length > 0 && (
              <div className="sc-warnings" role="note" data-demo={sc.run.provider === "demo"}>
                <p>{sc.warnings[0]}</p>
              </div>
            )}
            <div className="ov-results">
              <div className="ov-headline">
                <p className="rv-small mono">
                  Run {sc.run.created_at.replace("T", " ").slice(0, 16)} · {sc.run.provider}/{sc.run.model} · {sc.n_cases} cases
                </p>
                <p className="ov-line">
                  <span className="eyebrow">Top-1 diagnosis</span>
                  <span className="serif ov-big">{pct(rate("dx_top1", first))}</span>
                  <span className="ov-arrow">→</span>
                  <span className="serif ov-big">{pct(rate("dx_top1", last))}</span>
                  <span className="mono rv-small">{first} → {last}</span>
                </p>
                <p className="ov-line">
                  <span className="eyebrow">Any dangerous error</span>
                  <span className="serif ov-big">{pct(rate("dangerous", first))}</span>
                  <span className="ov-arrow">→</span>
                  <span className="serif ov-big">{pct(rate("dangerous", last))}</span>
                  <span className="mono rv-small">{first} → {last} · lower is better</span>
                </p>
              </div>
              {danger && <DotWhisker metric={danger} conditions={conds} />}
            </div>
          </>
        )}
      </section>

      <div className="st-two">
        <section className="ov-section">
          <h2 className="sc-h2">How to use it</h2>
          <ol className="st-list">
            <li><Link to="/">Bench</Link> — pick a case, press R, watch each condition’s trace stream in.</li>
            <li><Link to="/scorecard">Scorecard</Link> — rates with 95% intervals and McNemar tests; export CSV.</li>
            <li><Link to="/review">Review</Link> — a veterinarian rates answers blind; agreement with the scorer as Cohen’s κ.</li>
            <li><Link to="/cases">Cases</Link> and <Link to="/drugs">Drug Table</Link> — edit and verify the data.</li>
            <li><Link to="/study">Study design</Link> — conditions, metrics, statistics and limitations.</li>
          </ol>
        </section>
        <section className="ov-section">
          <h2 className="sc-h2">Recent runs</h2>
          <ul className="ov-runs">
            {(runs ?? []).slice(0, 5).map((r) => (
              <li key={r.id} className="mono">
                {r.created_at.replace("T", " ").slice(0, 16)} · {r.provider} · {r.case_ids.length}×{r.conditions.length}
                {r.interview ? " · interview" : ""} · {r.status}
              </li>
            ))}
            {runs && runs.length === 0 && <li>No runs yet.</li>}
          </ul>
          <Link className="link-button" to="/runs">All runs</Link>
        </section>
      </div>
    </div>
  );
}
