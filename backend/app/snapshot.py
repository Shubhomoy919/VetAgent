"""Frozen results snapshots: one complete live run, exported to JSON and shipped with the release.

A deployed site loads the snapshot into an empty database at startup, so the public pages show real numbers
without anyone spending API credits. `expected_scorecard` lets anyone check that scoring the snapshot again
gives the same numbers (`python -m app.scripts.snapshot verify`).
"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.data.benchmark import DISCLAIMER, benchmark_info
from app.data.loaders import load_cases
from app.scoring.metrics import build_scorecard
from app.storage.db import Store

FORMAT = 1
RESULT_FIELDS = ("case_id", "condition", "interview", "status", "answer", "error", "trace", "rules_fired",
                 "owner_questions", "steps", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "cached",
                 "cache_key", "created_at")


class SnapshotError(Exception):
    pass


def _metric_summary(sc: dict[str, Any]) -> dict[str, Any]:
    """The numbers that must reproduce: k/n per metric and condition."""
    return {m["key"]: {c: {"k": v["k"], "n": v["n"]} for c, v in m["by_condition"].items()} for m in sc["metrics"]}


def export_run(store: Store, run_id: str) -> dict[str, Any]:
    run = store.get_run(run_id)
    if run is None:
        raise SnapshotError(f"No run {run_id}")
    if run["provider"] == "demo":
        raise SnapshotError("Demo runs cannot be released as a snapshot")
    results = [{k: r[k] for k in RESULT_FIELDS} for r in store.results(run_id)]
    cases = {c.case_id: c for c in load_cases()}
    sc = build_scorecard(run, store.results(run_id), cases)
    run_out = {k: v for k, v in run.items() if k not in ("tokens", "errors", "cost_unknown")}
    return {
        "format": FORMAT,
        "disclaimer": DISCLAIMER,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "benchmark": {k: benchmark_info()[k] for k in ("version", "hash", "n_cases", "n_drugs")},
        "run": run_out,
        "results": results,
        "expected_scorecard": _metric_summary(sc),
    }


def write_snapshot(data: dict[str, Any], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path.with_suffix(".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8", newline="\n")
    return digest


def read_snapshot(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    sums = path.with_suffix(".sha256")
    if sums.is_file():
        expected = sums.read_text(encoding="utf-8").split()[0]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise SnapshotError(f"{path.name} does not match its .sha256 file")
    data = json.loads(raw)
    if data.get("format") != FORMAT:
        raise SnapshotError(f"Unsupported snapshot format {data.get('format')!r}")
    if data["run"]["provider"] == "demo":
        raise SnapshotError("Snapshot contains a demo run")
    return data


def load_snapshot(store: Store, path: Path) -> str | None:
    """Insert the snapshot run if it is not in the database yet. Returns the run id, or None if already there."""
    data = read_snapshot(path)
    run = data["run"]
    if store.run_exists(run["id"]):
        return None
    store.import_run(run, data["results"])
    return run["id"]


def verify_snapshot(path: Path) -> list[str]:
    """Score the snapshot again and list any metric that differs from the numbers stored in it."""
    data = read_snapshot(path)
    cases = {c.case_id: c for c in load_cases()}
    results = [{**r, "id": i + 1, "run_id": data["run"]["id"]} for i, r in enumerate(data["results"])]
    got = _metric_summary(build_scorecard(data["run"], results, cases))
    want = data["expected_scorecard"]
    problems = [f"{key}: expected {want.get(key)}, got {got.get(key)}" for key in sorted(set(got) | set(want))
                if got.get(key) != want.get(key)]
    b = benchmark_info()
    if data["benchmark"]["hash"] != b["hash"]:
        problems.append(f"benchmark hash differs: snapshot {data['benchmark']['hash'][:12]}, data {b['short_hash']}")
    return problems
