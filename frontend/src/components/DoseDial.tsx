import { motion } from "motion/react";
import type { CaseDose } from "../api/cases";
import { Stamp } from "./Stamp";
import "./DoseDial.css";

const CX = 100;
const CY = 96;
const R = 78;

/** Point on the dial for a fraction 0..1 (left → right across the top semicircle). */
function pt(f: number, r = R): [number, number] {
  const a = Math.PI * (1 - f);
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
}

function arc(f0: number, f1: number, r = R): string {
  const [x0, y0] = pt(f0, r);
  const [x1, y1] = pt(f1, r);
  return `M${x0.toFixed(2)} ${y0.toFixed(2)}A${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

interface Props {
  dose: CaseDose;
  /** The model's computed dose in mg (null if it gave none). */
  modelDose: number | null;
  seed: string;
}

/** Dose dial: a semicircular instrument gauge. The safe band (drug table mg/kg × this animal's weight,
 *  computed in Python) is drawn in leaf and the needle points at the model's dose. A contraindicated or
 *  banned drug greys the dial and lands a DO NOT GIVE stamp; no sourced range shows NO DATA — UNVERIFIED.
 *  Nothing is ever estimated here. */
export function DoseDial({ dose, modelDose, seed }: Props) {
  const banned = dose.status === "banned_in_india" || dose.status === "contraindicated";
  const band = !banned ? dose.dose_mg_total ?? null : null;
  const noData = !banned && band === null;
  const scaleMax = band ? Math.max(band.max * 2, (modelDose ?? 0) * 1.25) : Math.max((modelDose ?? 0) * 1.5, 1);
  const f = (v: number) => Math.min(Math.max(v / scaleMax, 0), 1);
  const outside = band && modelDose !== null && (modelDose < band.min - 1e-9 || modelDose > band.max + 1e-9);
  const needleDeg = modelDose !== null && !noData ? -90 + f(modelDose) * 180 : null;

  const bandLo = band ? f(band.min) : 0;
  // A single-value band (min = max) still needs a visible mark: draw at least 3% of the arc around it.
  const bandHi = band ? Math.max(f(band.max), bandLo + 0.03) : 0;

  const verified = dose.verified ? "verified" : "UNVERIFIED";
  const label = banned
    ? `Dose dial for ${dose.drug}: do not give — ${dose.status === "banned_in_india" ? "banned for animal use in India" : "contraindicated"} (drug table, ${verified}).${modelDose !== null ? ` The model still gave ${fmt(modelDose)} mg.` : ""}`
    : noData
      ? `Dose dial for ${dose.drug}: no sourced dose range in the drug table (no data, unverified).${modelDose !== null ? ` Model dose ${fmt(modelDose)} mg.` : ""}`
      : `Dose dial for ${dose.drug}: table band ${fmt(band!.min)}–${fmt(band!.max)} mg for ${dose.weight_kg} kg (${verified}); model dose ${modelDose === null ? "not given" : `${fmt(modelDose)} mg${outside ? ", outside the band" : ", inside the band"}`}.`;

  const ticks = Array.from({ length: 11 }, (_, i) => i / 10);
  return (
    <figure className="dial" data-state={banned ? "banned" : noData ? "nodata" : outside ? "outside" : "ok"} role="img" aria-label={label} data-testid="dose-dial">
      <svg viewBox="0 0 200 108" className="dial-svg" aria-hidden="true">
        <path className="dial-track" d={arc(0, 1)} />
        {ticks.map((t) => {
          const [x0, y0] = pt(t, R + 6);
          const major = Math.round(t * 10) % 5 === 0;
          const [x1, y1] = pt(t, R + (major ? 14 : 10));
          return <line key={t} className="dial-tick" x1={x0} y1={y0} x2={x1} y2={y1} />;
        })}
        {band && <path className="dial-band" d={arc(bandLo, bandHi)} />}
        {needleDeg !== null && (
          <motion.g
            className="dial-needle"
            style={{ originX: `${CX}px`, originY: `${CY}px` }}
            initial={{ rotate: -90 }}
            animate={{ rotate: [-90, needleDeg + 7, needleDeg - 2, needleDeg] }}
            transition={{ duration: 0.32, times: [0, 0.6, 0.85, 1], ease: [0.2, 0.8, 0.2, 1] }}
          >
            <line x1={CX} y1={CY} x2={CX} y2={CY - R + 6} />
          </motion.g>
        )}
        <circle className="dial-hub" cx={CX} cy={CY} r={4} />
      </svg>
      <figcaption className="dial-read">
        <span className="dial-drug mono">{dose.drug}</span>
        {banned ? (
          <span className="dial-note">
            {dose.status === "banned_in_india" ? "Banned for animal use in India" : `Contraindicated in ${dose.species}`}
            {modelDose !== null && <span className="dial-bad"> · model dosed {fmt(modelDose)} mg</span>}
          </span>
        ) : noData ? (
          <span className="dial-note dial-nodata mono">NO DATA — UNVERIFIED{modelDose !== null ? ` · model ${fmt(modelDose)} mg` : ""}</span>
        ) : (
          <>
            <span className="dial-value serif">{modelDose === null ? "—" : `${fmt(modelDose)} mg`}</span>
            <span className="dial-note mono">
              band {fmt(band!.min)}
              {band!.max !== band!.min ? `–${fmt(band!.max)}` : ""} mg · {fmt(dose.dose_mg_per_kg!.min)}
              {dose.dose_mg_per_kg!.max !== dose.dose_mg_per_kg!.min ? `–${fmt(dose.dose_mg_per_kg!.max)}` : ""} mg/kg × {dose.weight_kg} kg
              {!dose.verified && " · UNVERIFIED"}
            </span>
          </>
        )}
      </figcaption>
      {banned && (
        <span className="dial-stamp">
          <Stamp kind="DO NOT GIVE" seed={seed} delay={0.18} />
        </span>
      )}
    </figure>
  );
}
