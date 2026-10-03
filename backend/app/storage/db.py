"""SQLite storage for runs, per-condition results and the answer cache (data/runs.db)."""

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import DATA_DIR

DB_PATH = DATA_DIR / "runs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    conditions TEXT NOT NULL,
    case_ids TEXT NOT NULL,
    interview INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'running',
    n_total INTEGER NOT NULL,
    n_done INTEGER NOT NULL DEFAULT 0,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    case_id TEXT NOT NULL,
    condition TEXT NOT NULL,
    interview INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    answer TEXT,
    error TEXT,
    trace TEXT NOT NULL,
    rules_fired TEXT NOT NULL DEFAULT '[]',
    owner_questions TEXT NOT NULL DEFAULT '[]',
    steps INTEGER NOT NULL DEFAULT 0,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    cached INTEGER NOT NULL DEFAULT 0,
    cache_key TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS results_run ON results(run_id);
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    condition TEXT NOT NULL,
    case_id TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    interview INTEGER NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER NOT NULL REFERENCES results(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    rating TEXT NOT NULL CHECK (rating IN ('acceptable', 'unacceptable', 'unsure')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (result_id, reviewer)
);
CREATE INDEX IF NOT EXISTS reviews_result ON reviews(result_id);
"""

_lock = threading.Lock()


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with _lock:
                yield conn
                conn.commit()
        finally:
            conn.close()

    # ---------- runs ----------
    def create_run(
        self, *, provider: str, model: str, prompt_version: str, conditions: list[str], case_ids: list[str],
        interview: bool, label: str = "",
    ) -> str:
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        with self._conn() as c:
            c.execute(
                "INSERT INTO runs (id, created_at, label, provider, model, prompt_version, conditions, case_ids, "
                "interview, n_total) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, now(), label, provider, model, prompt_version, json.dumps(conditions), json.dumps(case_ids),
                 int(interview), len(conditions) * len(case_ids)),
            )
        return run_id

    def finish_run(self, run_id: str, status: str = "done") -> None:
        with self._conn() as c:
            c.execute("UPDATE runs SET status=?, finished_at=? WHERE id=?", (status, now(), run_id))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return _run_dict(row) if row else None

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Runs, newest first, with token, error and cost totals over their results."""
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT u.*,
                       COALESCE(SUM(r.tokens_in + r.tokens_out), 0) AS tokens,
                       COALESCE(SUM(CASE WHEN r.status != 'ok' THEN 1 ELSE 0 END), 0) AS errors,
                       SUM(r.cost_usd) AS cost_usd,
                       COALESCE(SUM(CASE WHEN r.id IS NOT NULL AND r.cost_usd IS NULL THEN 1 ELSE 0 END), 0) AS cost_unknown
                FROM runs u LEFT JOIN results r ON r.run_id = u.id
                GROUP BY u.id
                ORDER BY u.created_at DESC, u.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out = []
        for row in rows:
            d = _run_dict(row)
            if d["cost_unknown"]:
                d["cost_usd"] = None
            out.append(d)
        return out

    def usage_totals(self) -> list[dict[str, Any]]:
        """Token and cost totals per provider/model across all stored results."""
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT u.provider, u.model, COUNT(r.id) AS results,
                       COALESCE(SUM(r.tokens_in), 0) AS tokens_in, COALESCE(SUM(r.tokens_out), 0) AS tokens_out,
                       SUM(r.cost_usd) AS cost_usd,
                       COALESCE(SUM(CASE WHEN r.cost_usd IS NULL THEN 1 ELSE 0 END), 0) AS cost_unknown
                FROM results r JOIN runs u ON u.id = r.run_id
                GROUP BY u.provider, u.model ORDER BY results DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- reviews ----------
    def save_review(self, result_id: int, reviewer: str, rating: str, note: str = "") -> dict[str, Any]:
        ts = now()
        with self._conn() as c:
            if c.execute("SELECT 1 FROM results WHERE id=?", (result_id,)).fetchone() is None:
                raise KeyError(f"No result {result_id}")
            c.execute(
                "INSERT INTO reviews (result_id, reviewer, rating, note, created_at, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(result_id, reviewer) DO UPDATE SET rating=excluded.rating, note=excluded.note, "
                "updated_at=excluded.updated_at",
                (result_id, reviewer, rating, note, ts, ts),
            )
            row = c.execute("SELECT * FROM reviews WHERE result_id=? AND reviewer=?", (result_id, reviewer)).fetchone()
        return dict(row)

    def delete_review(self, result_id: int, reviewer: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM reviews WHERE result_id=? AND reviewer=?", (result_id, reviewer))
            return cur.rowcount > 0

    def reviews_for_run(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT v.* FROM reviews v JOIN results r ON r.id = v.result_id WHERE r.run_id=? ORDER BY v.id",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- results ----------
    def add_result(self, run_id: str, r: dict[str, Any]) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO results (run_id, case_id, condition, interview, status, answer, error, trace, rules_fired, "
                "owner_questions, steps, tokens_in, tokens_out, cost_usd, latency_ms, cached, cache_key, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id, r["case_id"], r["condition"], int(r["interview"]), r["status"],
                    json.dumps(r["answer"]) if r.get("answer") is not None else None,
                    r.get("error"), json.dumps(r["trace"]), json.dumps(r.get("rules_fired", [])),
                    json.dumps(r.get("owner_questions", [])), r.get("steps", 0), r.get("tokens_in", 0),
                    r.get("tokens_out", 0), r.get("cost_usd"), r.get("latency_ms", 0), int(r.get("cached", False)),
                    r.get("cache_key"), now(),
                ),
            )
            c.execute("UPDATE runs SET n_done = n_done + 1 WHERE id=?", (run_id,))
            return int(cur.lastrowid or 0)

    def results(self, run_id: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM results WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
        return [_result_dict(r) for r in rows]

    def get_result(self, result_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT r.*, u.provider, u.model FROM results r JOIN runs u ON u.id = r.run_id WHERE r.id=?",
                (result_id,),
            ).fetchone()
        return _result_dict(row) if row else None

    def latest_results(self, interview: bool) -> list[dict[str, Any]]:
        """Most recent result per (case, condition) for the given mode, without traces."""
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT r.id, r.run_id, r.case_id, r.condition, r.interview, r.status, r.answer, r.error,
                       r.rules_fired, r.owner_questions, r.steps, r.tokens_in, r.tokens_out, r.cost_usd,
                       r.latency_ms, r.cached, r.created_at, u.provider, u.model
                FROM results r
                JOIN (SELECT case_id, condition, MAX(id) AS mid FROM results WHERE interview=?
                      GROUP BY case_id, condition) m ON m.mid = r.id
                JOIN runs u ON u.id = r.run_id
                """,
                (int(interview),),
            ).fetchall()
        out = []
        for row in rows:
            d = dict(row)
            for k in ("answer", "rules_fired", "owner_questions"):
                d[k] = json.loads(d[k]) if d[k] is not None else None
            d["interview"] = bool(d["interview"])
            d["cached"] = bool(d["cached"])
            out.append(d)
        return out

    # ---------- cache ----------
    def cache_get(self, key: str) -> dict[str, Any] | None:
        with self._conn() as c:
            row = c.execute("SELECT payload FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def cache_put(self, key: str, meta: dict[str, Any], payload: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO cache (key, provider, model, condition, case_id, prompt_version, interview, "
                "payload, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (key, meta["provider"], meta["model"], meta["condition"], meta["case_id"], meta["prompt_version"],
                 int(meta["interview"]), json.dumps(payload), now()),
            )

    def count_runs(self) -> int:
        with self._conn() as c:
            return int(c.execute("SELECT COUNT(*) FROM runs").fetchone()[0])


def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["conditions"] = json.loads(d["conditions"])
    d["case_ids"] = json.loads(d["case_ids"])
    d["interview"] = bool(d["interview"])
    return d


def _result_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for k in ("answer", "trace", "rules_fired", "owner_questions"):
        if k in d:
            d[k] = json.loads(d[k]) if d[k] is not None else None
    d["interview"] = bool(d["interview"])
    d["cached"] = bool(d["cached"])
    return d
