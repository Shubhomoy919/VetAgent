import { motion } from "motion/react";
import { useLayoutEffect, useRef, useState } from "react";
import type { ConditionId } from "../../api/runs";
import { pct, type MetricRow } from "../../api/scorecard";
import { CONDITIONS } from "../../app/conditions";

const ROW_H = 26;
const PAD = 8;
const EASE = [0.2, 0.8, 0.2, 1] as const;

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.floor(e?.contentRect.width ?? 0)));
    ro.observe(el);
    setW(Math.floor(el.getBoundingClientRect().width));
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const NAME = Object.fromEntries(CONDITIONS.map((c) => [c.id, c.name])) as Record<ConditionId, string>;

/** One metric: a row per condition with the rate (dot) and its Wilson 95% CI (whisker) on a 0–100% scale. */
export function DotWhisker({ metric, conditions }: { metric: MetricRow; conditions: ConditionId[] }) {
  const [trackRef, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<ConditionId | null>(null);
  const x = (v: number) => PAD + v * Math.max(0, width - 2 * PAD);
  const ticks = [0, 0.25, 0.5, 0.75, 1];

  return (
    <figure className="dw" data-testid={`chart-${metric.key}`}>
      <figcaption className="dw-head">
        <span className="dw-title">{metric.label}</span>
        <span className="dw-dir mono" data-danger={metric.danger}>
          {metric.better === "higher" ? "↑ higher is better" : "↓ lower is better"}
        </span>
      </figcaption>
      <div className="dw-grid">
        {conditions.map((cond, i) => {
          const r = metric.by_condition[cond];
          const has = r && r.rate !== null && r.lo !== null && r.hi !== null;
          const label = `${cond} ${NAME[cond]}: ${metric.label} ${
            has ? `${pct(r.rate, 1)} (95% CI ${pct(r.lo, 1)}–${pct(r.hi, 1)}), ${r.k} of ${r.n}` : "not applicable (n = 0)"
          }`;
          return (
            <div
              key={cond}
              className="dw-row"
              data-cond={cond}
              tabIndex={0}
              aria-label={label}
              onMouseEnter={() => setHover(cond)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(cond)}
              onBlur={() => setHover(null)}
            >
              <span className="dw-label mono">
                <span className="dw-swatch" aria-hidden="true" />
                {cond}
              </span>
              <div className="dw-track" ref={i === 0 ? trackRef : undefined}>
                {width > 0 && (
                  <svg width={width} height={ROW_H} aria-hidden="true">
                    {ticks.map((t) => (
                      <line key={t} x1={x(t)} x2={x(t)} y1={2} y2={ROW_H - 2} className="dw-tick" />
                    ))}
                    {has && (
                      <>
                        <motion.line
                          x1={x(r.lo as number)}
                          x2={x(r.hi as number)}
                          y1={ROW_H / 2}
                          y2={ROW_H / 2}
                          className="dw-whisker"
                          initial={{ pathLength: 0 }}
                          animate={{ pathLength: 1 }}
                          transition={{ duration: 0.26, ease: EASE, delay: i * 0.04 }}
                        />
                        <line x1={x(r.lo as number)} x2={x(r.lo as number)} y1={ROW_H / 2 - 4} y2={ROW_H / 2 + 4} className="dw-cap" />
                        <line x1={x(r.hi as number)} x2={x(r.hi as number)} y1={ROW_H / 2 - 4} y2={ROW_H / 2 + 4} className="dw-cap" />
                        <circle cx={x(r.rate as number)} cy={ROW_H / 2} r={hover === cond ? 6 : 5} className="dw-dot" />
                      </>
                    )}
                  </svg>
                )}
                {hover === cond && has && width > 0 && (
                  <div className="dw-tip mono" role="presentation" style={{ left: Math.min(Math.max(x(r.rate as number), 70), width - 70) }}>
                    <strong>{pct(r.rate, 1)}</strong> {r.k}/{r.n}
                    <br />
                    CI {pct(r.lo, 1)}–{pct(r.hi, 1)}
                  </div>
                )}
              </div>
              <span className="dw-value mono">
                {has ? (
                  <>
                    {pct(r.rate)} <span className="dw-n">{r.k}/{r.n}</span>
                  </>
                ) : (
                  <span className="dw-n">n/a</span>
                )}
              </span>
            </div>
          );
        })}
        <div className="dw-axis" aria-hidden="true">
          <span />
          <div className="dw-axis-track">
            {width > 0 &&
              ticks.map((t) => (
                <span key={t} className="mono" style={{ left: x(t) }}>
                  {t * 100}
                </span>
              ))}
          </div>
          <span className="dw-n mono">%</span>
        </div>
      </div>
    </figure>
  );
}
