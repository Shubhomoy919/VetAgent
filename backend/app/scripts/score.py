"""Score a run and export the scorecard.

    python -m app.scripts.score                       # latest multi-case run
    python -m app.scripts.score 20261003-140616-bd0853 --csv ../data/exports/scorecard.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from app.config import DATA_DIR
from app.data.loaders import load_cases
from app.scoring.metrics import CSV_HEADER, build_scorecard, scorecard_csv_rows
from app.storage.db import Store


def _pct(r: dict) -> str:
    if r["rate"] is None:
        return "—"
    return f"{r['rate'] * 100:5.1f}% [{r['lo'] * 100:4.1f}–{r['hi'] * 100:5.1f}] {r['k']}/{r['n']}"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_id", nargs="?", default=None)
    ap.add_argument("--csv", type=Path, default=None, help="CSV path (default data/exports/scorecard-<run>.csv)")
    ap.add_argument("--json", type=Path, default=None, help="also write the full scorecard JSON here")
    args = ap.parse_args(argv)

    store = Store()
    run_id = args.run_id
    if run_id is None:
        runs = [r for r in store.list_runs(200) if r["n_done"] > 0 and len(r["case_ids"]) > 1]
        if not runs:
            print("No multi-case runs found.", file=sys.stderr)
            return 2
        run_id = runs[0]["id"]
    run = store.get_run(run_id)
    if run is None:
        print(f"No run {run_id}", file=sys.stderr)
        return 2

    sc = build_scorecard(run, store.results(run_id), {c.case_id: c for c in load_cases()})
    print(f"Run {run_id} · {run['provider']}/{run['model']} · {sc['n_cases']} cases · conditions {', '.join(sc['conditions'])}")
    for w in sc["warnings"]:
        print(f"  ! {w}")
    print()
    width = 26
    print(f"  {'metric':<{width}}" + "".join(f"{c:<32}" for c in sc["conditions"]))
    for m in sc["metrics"]:
        arrow = "↑" if m["better"] == "higher" else "↓"
        print(f"  {m['label'] + ' ' + arrow:<{width}}" + "".join(f"{_pct(m['by_condition'][c]):<32}" for c in sc["conditions"]))
    print("\n  McNemar (exact, two-sided), adjacent conditions:")
    for t in sc["mcnemar"]:
        if t["metric"] in ("dx_top1", "dangerous"):
            p = (
                "n/a (no discordant pairs)" if t["p"] is None
                else "p<0.001" if t["p"] < 0.001 else f"p={t['p']:.3f}"
            )
            print(f"    {t['metric']:<12} {t['a']}→{t['b']}: only {t['a']}={t['only_a']}, only {t['b']}={t['only_b']}, {p}")

    out = args.csv or (DATA_DIR / "exports" / f"scorecard-{run_id}.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        w.writerows(scorecard_csv_rows(sc))
    print(f"\nCSV written: {out.resolve()}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(sc, indent=2), encoding="utf-8")
        print(f"JSON written: {args.json.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
