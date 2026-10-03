"""Run one or more cases through the conditions and store the results.

    python -m app.scripts.run_case BOV-WD-007
    python -m app.scripts.run_case BOV-WD-007 CAP-001 --conditions C0,C4 --force
    python -m app.scripts.run_case CAN-013 --interview          # owner-interview mode (C0, C3)
"""

import argparse
import json
import sys

from app.agent.conditions import CONDITIONS, INTERVIEW_CONDITIONS
from app.agent.prompts import PROMPT_VERSION
from app.agent.runner import run_one
from app.config import get_settings
from app.data.loaders import DataError, load_cases, load_drugs
from app.llm.factory import get_provider
from app.retrieval.service import svtg_index
from app.storage.db import Store


def _trace_line(step: dict) -> str:
    tok = f" {step['tokens_in']}→{step['tokens_out']} tok" if step["tokens_in"] or step["tokens_out"] else ""
    return f"    {step['index']:>2}. {step['kind']:<6} {step['name']:<22} {step['latency_ms']:>5} ms{tok}"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("case_ids", nargs="+")
    ap.add_argument("--conditions", default=None, help="comma-separated, default all (C0–C4; C0,C3 in interview)")
    ap.add_argument("--interview", action="store_true", help="owner-interview mode")
    ap.add_argument("--force", action="store_true", help="ignore the cache")
    ap.add_argument("--quiet", action="store_true", help="summary only, no answer JSON")
    args = ap.parse_args(argv)

    settings = get_settings()
    try:
        cases = {c.case_id: c for c in load_cases()}
        drugs = load_drugs()
    except DataError as e:
        print(f"Data error: {e}", file=sys.stderr)
        return 2
    missing = [cid for cid in args.case_ids if cid not in cases]
    if missing:
        print(f"Unknown case id(s): {', '.join(missing)}", file=sys.stderr)
        return 2

    default = INTERVIEW_CONDITIONS if args.interview else CONDITIONS
    conditions = [c.strip().upper() for c in args.conditions.split(",")] if args.conditions else list(default)
    bad = [c for c in conditions if c not in (INTERVIEW_CONDITIONS if args.interview else CONDITIONS)]
    if bad:
        print(f"Invalid condition(s) for this mode: {', '.join(bad)}", file=sys.stderr)
        return 2

    provider = get_provider(settings)
    index = svtg_index(settings)
    store = Store()
    run_id = store.create_run(
        provider=provider.name, model=provider.model, prompt_version=PROMPT_VERSION, conditions=conditions,
        case_ids=args.case_ids, interview=args.interview, label="cli",
    )
    mode = "DEMO (sample responses, not live model output)" if provider.name == "demo" else "LIVE"
    print(f"Run {run_id} · provider={provider.name} model={provider.model} · {mode} · prompt {PROMPT_VERSION}")
    print(f"SVTG index: {len(index)} chunks · interview={args.interview} · force={args.force}\n")

    summary = []
    failures = 0
    quota_stop = False
    for cid in args.case_ids:
        if quota_stop:
            break
        for cond in conditions:
            r = run_one(case=cases[cid], condition=cond, provider=provider, settings=settings, index=index,
                        drugs=drugs, store=store, interview=args.interview, force=args.force)
            store.add_result(run_id, r)
            print(f"=== {cid} · {cond}{' (interview)' if args.interview else ''} · {r['status']}"
                  f"{' · cached' if r['cached'] else ''} ===")
            if r["status"] != "ok":
                failures += 1
                print(f"  ERROR: {r['error']}")
            if r.get("quota_exhausted"):
                print("  Stopping: quota will not recover during this run. Finished results are kept; "
                      "re-run later and cached results are reused.")
                quota_stop = True
                break
            elif not args.quiet:
                print(json.dumps(r["answer"], indent=2, ensure_ascii=False))
            print("  trace:")
            for s in r["trace"]:
                print(_trace_line(s))
            if r["rules_fired"]:
                print("  rules fired: " + "; ".join(f"{f['rule']} ({f['detail']})" for f in r["rules_fired"]))
            if r["owner_questions"]:
                print("  owner questions: " + " | ".join(r["owner_questions"]))
            print()
            a = r["answer"] or {}
            summary.append((cid, cond, r["status"], a.get("most_likely", "—"), a.get("triage", "—"),
                            a.get("drug_status", "—"), a.get("withdrawal_days"), r["steps"],
                            [c.get("page") for c in a.get("citations", [])]))
    store.finish_run(run_id, "quota_exhausted" if quota_stop else "done" if failures == 0 else "done_with_errors")

    print("Summary")
    print(f"  {'case':<12} {'cond':<4} {'status':<6} {'most_likely':<34} {'triage':<9} {'drug':<15} {'wd':>4} {'steps':>5}  pages")
    for cid, cond, st, ml, tr, ds, wd, steps, pages in summary:
        wd_s = "—" if wd is None else f"{wd:g}"
        print(f"  {cid:<12} {cond:<4} {st:<6} {str(ml)[:34]:<34} {tr:<9} {ds:<15} {wd_s:>4} {steps:>5}  {pages}")
    print(f"\nStored in data/runs.db as run {run_id}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
