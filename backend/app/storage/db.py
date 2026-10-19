"""Storage for runs, results, traces, the answer cache, reviews, the benchmark data, SVTG passages, saved settings,
rate-limit and lockout counters and the daily token budget.

DATABASE_URL selects the database: Postgres in production (Vercel Marketplace, e.g. Neon), SQLite
(data/vetagentbench.db) when it is not set. On SQLite the tables are created on first use; Postgres is set up
with Alembic (`alembic upgrade head`, see docs/DEPLOY.md). Nothing here writes to the filesystem except the local
SQLite file.
"""

import json
import random
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, and_, case, create_engine, delete, event, func, select, true, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import DATA_DIR, configured_database_url, env_settings
from app.storage import schema as t

DEFAULT_SQLITE = DATA_DIR / "vetagentbench.db"


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def utc_day(ts: datetime | None = None) -> str:
    return (ts or datetime.now(UTC)).strftime("%Y-%m-%d")


def normalize_url(url: str) -> str:
    """Neon and other hosts give postgres:// or postgresql:// URLs; use the psycopg 3 driver for both."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class DatabaseNotConfigured(RuntimeError):
    """Production needs DATABASE_URL: serverless functions have no persistent filesystem for SQLite."""


def database_url() -> str:
    url = configured_database_url()
    if url:
        return normalize_url(url)
    if env_settings().is_production:
        raise DatabaseNotConfigured("DATABASE_URL is not set. Add a Postgres database (docs/DEPLOY.md, step 3).")
    return f"sqlite:///{DEFAULT_SQLITE.as_posix()}"


def describe_url(url: str) -> str:
    """Engine name for health output; never the URL itself (it contains the password)."""
    return "postgresql" if url.startswith("postgresql") else "sqlite"


_engines: dict[str, Engine] = {}
_engines_lock = threading.Lock()
_created: set[str] = set()
_sqlite_write = threading.Lock()


def get_engine(url: str) -> Engine:
    with _engines_lock:
        eng = _engines.get(url)
        if eng is None:
            if url.startswith("sqlite"):
                eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

                @event.listens_for(eng, "connect")
                def _fk_on(dbapi_conn, _):  # noqa: ANN001
                    dbapi_conn.execute("PRAGMA foreign_keys = ON")
            else:
                # Pooled serverless connections: small pool, checked before use, recycled; no server-side
                # prepared statements, so a transaction-mode pooler (PgBouncer) works.
                eng = create_engine(url, pool_size=3, max_overflow=2, pool_pre_ping=True, pool_recycle=300,
                                    connect_args={"prepare_threshold": None})
            _engines[url] = eng
        return eng


def dispose_engines() -> None:
    with _engines_lock:
        for eng in _engines.values():
            eng.dispose()
        _engines.clear()
        _created.clear()


class Store:
    def __init__(self, target: str | Path | None = None, hide_demo: bool | None = None):
        if target is None:
            url = database_url()
        elif isinstance(target, Path):
            target.parent.mkdir(parents=True, exist_ok=True)
            url = f"sqlite:///{target.as_posix()}"
        else:
            url = normalize_url(target)
        self.url = url
        self.engine = get_engine(url)
        self.dialect = self.engine.dialect.name
        self._hide_demo = hide_demo
        if self.dialect == "sqlite" and url not in _created:
            if url != "sqlite://":
                Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
            t.metadata.create_all(self.engine)
            _created.add(url)

    @property
    def engine_name(self) -> str:
        return describe_url(self.url)

    @property
    def hide_demo(self) -> bool:
        """Production never shows demo (sample) runs or results, even if some are still in the database."""
        if self._hide_demo is not None:
            return self._hide_demo
        from app.config import get_settings

        return get_settings().is_production

    def _vis(self):
        return t.runs.c.provider != "demo" if self.hide_demo else true()

    @contextmanager
    def _tx(self) -> Iterator[Connection]:
        """One transaction. SQLite allows one writer at a time, so local writes are serialised."""
        if self.dialect == "sqlite":
            with _sqlite_write, self.engine.begin() as conn:
                yield conn
        else:
            with self.engine.begin() as conn:
                yield conn

    def _insert(self, table):
        if self.dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        return insert(table)

    # ---------- runs ----------
    def create_run(
        self, *, provider: str, model: str, prompt_version: str, conditions: list[str], case_ids: list[str],
        interview: bool, label: str = "", temperature: float | None = None, benchmark_version: str | None = None,
        benchmark_hash: str | None = None, force: bool = False,
    ) -> str:
        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        ts = now()
        with self._tx() as c:
            c.execute(t.runs.insert().values(
                id=run_id, created_at=ts, updated_at=ts, label=label, provider=provider, model=model,
                prompt_version=prompt_version, conditions=conditions, case_ids=case_ids, interview=interview,
                force=force, status="running", n_total=len(conditions) * len(case_ids), n_done=0,
                temperature=temperature, benchmark_version=benchmark_version, benchmark_hash=benchmark_hash,
            ))
        return run_id

    def finish_run(self, run_id: str, status: str = "done") -> None:
        ts = now()
        with self._tx() as c:
            c.execute(update(t.runs).where(t.runs.c.id == run_id).values(status=status, finished_at=ts, updated_at=ts))

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = c.execute(select(t.runs).where(t.runs.c.id == run_id, self._vis())).first()
        return _run_dict(row._mapping) if row else None

    def active_run(self, stale_after_s: int) -> dict[str, Any] | None:
        """The newest run still marked running that made progress in the last `stale_after_s` seconds."""
        cutoff = (datetime.now(UTC) - timedelta(seconds=stale_after_s)).isoformat(timespec="seconds")
        with self.engine.connect() as c:
            row = c.execute(
                select(t.runs).where(t.runs.c.status == "running", t.runs.c.updated_at >= cutoff, self._vis())
                .order_by(t.runs.c.created_at.desc()).limit(1)
            ).first()
        return _run_dict(row._mapping) if row else None

    def expire_stale_runs(self, stale_after_s: int) -> int:
        """Runs left 'running' with no progress (closed browser, crash) can never finish; mark them interrupted."""
        cutoff = (datetime.now(UTC) - timedelta(seconds=stale_after_s)).isoformat(timespec="seconds")
        ts = now()
        with self._tx() as c:
            return c.execute(
                update(t.runs).where(t.runs.c.status == "running", func.coalesce(t.runs.c.updated_at, t.runs.c.created_at) < cutoff)
                .values(status="interrupted", finished_at=ts, updated_at=ts)
            ).rowcount

    def mark_interrupted(self) -> int:
        """Mark every run still 'running' as interrupted (local start-up, after a crash)."""
        ts = now()
        with self._tx() as c:
            return c.execute(update(t.runs).where(t.runs.c.status == "running")
                             .values(status="interrupted", finished_at=ts, updated_at=ts)).rowcount

    def done_keys(self, run_id: str) -> list[dict[str, Any]]:
        """(case, condition) pairs that already have a result in this run, oldest first."""
        with self.engine.connect() as c:
            rows = c.execute(select(t.results.c.case_id, t.results.c.condition, t.results.c.status)
                             .where(t.results.c.run_id == run_id).order_by(t.results.c.id)).all()
        return [dict(r._mapping) for r in rows]

    def list_runs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Runs, newest first, with token, error and cost totals over their results."""
        r, u = t.results, t.runs
        q = (
            select(
                u,
                func.coalesce(func.sum(r.c.tokens_in + r.c.tokens_out), 0).label("tokens"),
                func.coalesce(func.sum(case((r.c.status != "ok", 1), else_=0)), 0).label("errors"),
                func.sum(r.c.cost_usd).label("cost_usd"),
                func.coalesce(func.sum(case((and_(r.c.id.isnot(None), r.c.cost_usd.is_(None)), 1), else_=0)), 0).label("cost_unknown"),
            )
            .select_from(u.outerjoin(r, r.c.run_id == u.c.id))
            .where(self._vis())
            .group_by(u.c.id)
            .order_by(u.c.created_at.desc(), u.c.id.desc())
            .limit(limit)
        )
        with self.engine.connect() as c:
            rows = c.execute(q).all()
        out = []
        for row in rows:
            d = _run_dict(row._mapping)
            d["tokens"], d["errors"], d["cost_unknown"] = int(d["tokens"]), int(d["errors"]), int(d["cost_unknown"])
            if d["cost_unknown"]:
                d["cost_usd"] = None
            out.append(d)
        return out

    def usage_totals(self) -> list[dict[str, Any]]:
        """Token and cost totals per provider/model across all stored results."""
        r, u = t.results, t.runs
        q = (
            select(
                u.c.provider, u.c.model, func.count(r.c.id).label("results"),
                func.coalesce(func.sum(r.c.tokens_in), 0).label("tokens_in"),
                func.coalesce(func.sum(r.c.tokens_out), 0).label("tokens_out"),
                func.sum(r.c.cost_usd).label("cost_usd"),
                func.coalesce(func.sum(case((r.c.cost_usd.is_(None), 1), else_=0)), 0).label("cost_unknown"),
            )
            .select_from(r.join(u, u.c.id == r.c.run_id))
            .where(self._vis())
            .group_by(u.c.provider, u.c.model)
            .order_by(func.count(r.c.id).desc())
        )
        with self.engine.connect() as c:
            return [{k: (int(v) if k in ("results", "tokens_in", "tokens_out", "cost_unknown") else v)
                     for k, v in row._mapping.items()} for row in c.execute(q).all()]

    def count_runs(self) -> int:
        with self.engine.connect() as c:
            return int(c.execute(select(func.count()).select_from(t.runs).where(self._vis())).scalar_one())

    def run_exists(self, run_id: str) -> bool:
        with self.engine.connect() as c:
            return c.execute(select(t.runs.c.id).where(t.runs.c.id == run_id)).first() is not None

    def delete_demo_runs(self) -> int:
        """Remove every demo run with its results, traces and reviews, and demo cache rows. Returns runs removed."""
        with self._tx() as c:
            ids = select(t.results.c.id).join(t.runs, t.runs.c.id == t.results.c.run_id).where(t.runs.c.provider == "demo")
            c.execute(delete(t.reviews).where(t.reviews.c.result_id.in_(ids)))
            c.execute(delete(t.traces).where(t.traces.c.result_id.in_(ids)))
            c.execute(delete(t.results).where(t.results.c.id.in_(ids)))
            n = c.execute(delete(t.runs).where(t.runs.c.provider == "demo")).rowcount
            c.execute(delete(t.cache).where(t.cache.c.provider == "demo"))
        return n

    # ---------- reviews ----------
    def save_review(self, result_id: int, reviewer: str, rating: str, note: str = "") -> dict[str, Any]:
        if rating not in ("acceptable", "unacceptable", "unsure"):
            raise ValueError(f"Invalid rating {rating}")
        ts = now()
        with self._tx() as c:
            if c.execute(select(t.results.c.id).where(t.results.c.id == result_id)).first() is None:
                raise KeyError(f"No result {result_id}")
            stmt = self._insert(t.reviews).values(result_id=result_id, reviewer=reviewer, rating=rating, note=note,
                                                  created_at=ts, updated_at=ts)
            c.execute(stmt.on_conflict_do_update(
                index_elements=["result_id", "reviewer"],
                set_={"rating": stmt.excluded.rating, "note": stmt.excluded.note, "updated_at": stmt.excluded.updated_at},
            ))
            row = c.execute(select(t.reviews).where(t.reviews.c.result_id == result_id,
                                                    t.reviews.c.reviewer == reviewer)).first()
        return dict(row._mapping)  # type: ignore[union-attr]

    def delete_review(self, result_id: int, reviewer: str) -> bool:
        with self._tx() as c:
            return c.execute(delete(t.reviews).where(t.reviews.c.result_id == result_id,
                                                     t.reviews.c.reviewer == reviewer)).rowcount > 0

    def reviews_for_run(self, run_id: str) -> list[dict[str, Any]]:
        q = (select(t.reviews).join(t.results, t.results.c.id == t.reviews.c.result_id)
             .where(t.results.c.run_id == run_id).order_by(t.reviews.c.id))
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q).all()]

    # ---------- results ----------
    @staticmethod
    def _result_values(run_id: str, r: dict[str, Any], created_at: str) -> dict[str, Any]:
        return {
            "run_id": run_id, "case_id": r["case_id"], "condition": r["condition"], "interview": bool(r["interview"]),
            "status": r["status"], "answer": r.get("answer"), "error": r.get("error"),
            "rules_fired": r.get("rules_fired") or [], "owner_questions": r.get("owner_questions") or [],
            "steps": r.get("steps", 0), "tokens_in": r.get("tokens_in", 0), "tokens_out": r.get("tokens_out", 0),
            "cost_usd": r.get("cost_usd"), "latency_ms": r.get("latency_ms", 0), "cached": bool(r.get("cached", False)),
            "cache_key": r.get("cache_key"), "created_at": created_at,
        }

    def add_result(self, run_id: str, r: dict[str, Any], count_budget: bool = True) -> int:
        """Store a result and its trace, advance the run, and add live tokens to today's budget."""
        ts = now()
        with self._tx() as c:
            rid = int(c.execute(t.results.insert().values(**self._result_values(run_id, r, ts))).inserted_primary_key[0])
            c.execute(t.traces.insert().values(result_id=rid, steps=r.get("trace") or []))
            c.execute(update(t.runs).where(t.runs.c.id == run_id).values(n_done=t.runs.c.n_done + 1, updated_at=ts))
            tokens = int(r.get("tokens_in", 0)) + int(r.get("tokens_out", 0))
            if count_budget and tokens and not r.get("cached"):
                provider = c.execute(select(t.runs.c.provider).where(t.runs.c.id == run_id)).scalar_one_or_none()
                if provider and provider != "demo":
                    self._add_tokens(c, utc_day(), tokens)
        return rid

    def results(self, run_id: str) -> list[dict[str, Any]]:
        q = (select(t.results, t.traces.c.steps.label("trace"))
             .join(t.runs, t.runs.c.id == t.results.c.run_id)
             .outerjoin(t.traces, t.traces.c.result_id == t.results.c.id)
             .where(t.results.c.run_id == run_id, self._vis()).order_by(t.results.c.id))
        with self.engine.connect() as c:
            return [_result_dict(r._mapping) for r in c.execute(q).all()]

    def get_result(self, result_id: int) -> dict[str, Any] | None:
        q = (select(t.results, t.traces.c.steps.label("trace"), t.runs.c.provider, t.runs.c.model)
             .join(t.runs, t.runs.c.id == t.results.c.run_id)
             .outerjoin(t.traces, t.traces.c.result_id == t.results.c.id)
             .where(t.results.c.id == result_id, self._vis()))
        with self.engine.connect() as c:
            row = c.execute(q).first()
        return _result_dict(row._mapping) if row else None

    _SUMMARY = ("id", "run_id", "case_id", "condition", "interview", "status", "answer", "error", "rules_fired",
                "owner_questions", "steps", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "cached", "created_at")

    def case_results(self, case_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Every stored result for one case across runs, newest first, without traces."""
        cols = [t.results.c[k] for k in self._SUMMARY]
        q = (select(*cols, t.runs.c.provider, t.runs.c.model).join(t.runs, t.runs.c.id == t.results.c.run_id)
             .where(t.results.c.case_id == case_id, self._vis()).order_by(t.results.c.id.desc()).limit(limit))
        with self.engine.connect() as c:
            return [_result_dict(r._mapping) for r in c.execute(q).all()]

    def latest_results(self, interview: bool) -> list[dict[str, Any]]:
        """Most recent result per (case, condition) for the given mode, without traces."""
        x = t.results.alias("x")
        v = t.runs.alias("v")
        vis = (v.c.provider != "demo") if self.hide_demo else true()
        latest = (select(func.max(x.c.id).label("mid")).select_from(x.join(v, v.c.id == x.c.run_id))
                  .where(x.c.interview == interview, vis).group_by(x.c.case_id, x.c.condition).subquery())
        cols = [t.results.c[k] for k in self._SUMMARY]
        q = (select(*cols, t.runs.c.provider, t.runs.c.model)
             .join(latest, latest.c.mid == t.results.c.id).join(t.runs, t.runs.c.id == t.results.c.run_id))
        with self.engine.connect() as c:
            return [_result_dict(r._mapping) for r in c.execute(q).all()]

    def cited_pages(self) -> set[int]:
        """SVTG PDF pages cited by any visible stored answer."""
        q = (select(t.results.c.answer).join(t.runs, t.runs.c.id == t.results.c.run_id)
             .where(t.results.c.status == "ok", t.results.c.answer.isnot(None), self._vis()))
        pages: set[int] = set()
        with self.engine.connect() as c:
            for (answer,) in c.execute(q):
                for cit in (answer or {}).get("citations") or []:
                    page = cit.get("page") if isinstance(cit, dict) else None
                    if isinstance(page, int):
                        pages.add(page)
        return pages

    def import_run(self, run: dict[str, Any], results: list[dict[str, Any]]) -> None:
        """Insert a finished run and its results exactly as exported (timestamps kept), in one transaction.
        Imported results do not count against today's token budget."""
        with self._tx() as c:
            c.execute(t.runs.insert().values(
                id=run["id"], created_at=run["created_at"], updated_at=run.get("finished_at") or run["created_at"],
                label=run.get("label", ""), provider=run["provider"], model=run["model"],
                prompt_version=run["prompt_version"], conditions=run["conditions"], case_ids=run["case_ids"],
                interview=bool(run["interview"]), force=bool(run.get("force", False)), status=run["status"],
                n_total=run["n_total"], n_done=len(results), finished_at=run.get("finished_at"),
                temperature=run.get("temperature"), benchmark_version=run.get("benchmark_version"),
                benchmark_hash=run.get("benchmark_hash"),
            ))
            for r in results:
                rid = int(c.execute(t.results.insert().values(**self._result_values(run["id"], r, r["created_at"])))
                          .inserted_primary_key[0])
                c.execute(t.traces.insert().values(result_id=rid, steps=r.get("trace") or []))

    # ---------- answer cache ----------
    def cache_get(self, key: str) -> dict[str, Any] | None:
        with self.engine.connect() as c:
            row = c.execute(select(t.cache.c.payload).where(t.cache.c.key == key)).first()
        return dict(row[0]) if row else None

    def cache_put(self, key: str, meta: dict[str, Any], payload: dict[str, Any]) -> None:
        values = {"key": key, "provider": meta["provider"], "model": meta["model"], "condition": meta["condition"],
                  "case_id": meta["case_id"], "prompt_version": meta["prompt_version"],
                  "interview": bool(meta["interview"]), "payload": payload, "created_at": now()}
        with self._tx() as c:
            stmt = self._insert(t.cache).values(**values)
            c.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={
                "payload": stmt.excluded.payload, "created_at": stmt.excluded.created_at}))

    def cache_seed(self, key: str, meta: dict[str, Any], payload: dict[str, Any]) -> bool:
        """Add a cache entry only if the key is new (seeding from the snapshot). Returns True if added."""
        values = {"key": key, "provider": meta["provider"], "model": meta["model"], "condition": meta["condition"],
                  "case_id": meta["case_id"], "prompt_version": meta["prompt_version"],
                  "interview": bool(meta["interview"]), "payload": payload, "created_at": now()}
        with self._tx() as c:
            # RETURNING, not rowcount: psycopg reports -1 as the row count of an INSERT.
            stmt = self._insert(t.cache).values(**values).on_conflict_do_nothing(index_elements=["key"]).returning(t.cache.c.key)
            return c.execute(stmt).first() is not None

    # ---------- budget ----------
    def _add_tokens(self, c: Connection, day: str, tokens: int) -> None:
        stmt = self._insert(t.budget_usage).values(day=day, tokens=tokens)
        c.execute(stmt.on_conflict_do_update(index_elements=["day"], set_={"tokens": t.budget_usage.c.tokens + tokens}))

    def tokens_on(self, day: str) -> int:
        """Live-model tokens (in + out) spent on a UTC day. Cached, demo and imported answers cost nothing."""
        with self.engine.connect() as c:
            v = c.execute(select(t.budget_usage.c.tokens).where(t.budget_usage.c.day == day)).scalar_one_or_none()
        return int(v or 0)

    # ---------- benchmark data ----------
    def _bump(self, c: Connection, key: str) -> None:
        cur = c.execute(select(t.meta.c.value).where(t.meta.c.key == key)).scalar_one_or_none()
        nxt = f"{int((cur or "0").split(":")[0]) + 1}:{uuid.uuid4().hex[:8]}"
        if cur is None:
            c.execute(t.meta.insert().values(key=key, value=nxt))
        else:
            c.execute(update(t.meta).where(t.meta.c.key == key).values(value=nxt))

    def get_meta(self, key: str) -> str | None:
        with self.engine.connect() as c:
            return c.execute(select(t.meta.c.value).where(t.meta.c.key == key)).scalar_one_or_none()

    def set_meta(self, key: str, value: str) -> None:
        with self._tx() as c:
            stmt = self._insert(t.meta).values(key=key, value=value)
            c.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": stmt.excluded.value}))

    def data_rev(self) -> str:
        """Changes whenever cases or drug rows change (cache key for parsed data and the benchmark hash)."""
        return self.get_meta("data_rev") or "0"

    def case_records(self) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            return [dict(r[0]) for r in c.execute(select(t.cases.c.data).order_by(t.cases.c.position)).all()]

    def drug_records(self) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            return [dict(r[0]) for r in c.execute(select(t.drug_rows.c.data).order_by(t.drug_rows.c.position)).all()]

    def replace_cases(self, records: list[dict[str, Any]]) -> None:
        """Replace the whole case set in one transaction (records already validated, IDs unique)."""
        ts = now()
        with self._tx() as c:
            c.execute(delete(t.cases))
            if records:
                c.execute(t.cases.insert(), [{"case_id": r["case_id"], "position": i, "data": r, "updated_at": ts}
                                             for i, r in enumerate(records)])
            self._bump(c, "data_rev")

    def replace_drugs(self, records: list[dict[str, Any]]) -> None:
        ts = now()
        with self._tx() as c:
            c.execute(delete(t.drug_rows))
            if records:
                c.execute(t.drug_rows.insert(), [{"key": f"{r['species']}|{r['drug'].lower()}", "position": i,
                                                  "data": r, "updated_at": ts} for i, r in enumerate(records)])
            self._bump(c, "data_rev")

    # ---------- SVTG passages ----------
    def replace_chunks(self, chunks: list[dict[str, Any]], source: dict[str, Any]) -> None:
        with self._tx() as c:
            c.execute(delete(t.svtg_chunks))
            for start in range(0, len(chunks), 500):
                c.execute(t.svtg_chunks.insert(), [{**ch, "ord": start + i} for i, ch in enumerate(chunks[start:start + 500])])
            self._bump(c, "chunks_rev")
            stmt = self._insert(t.meta).values(key="svtg_source", value=json.dumps(source))
            c.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": stmt.excluded.value}))

    def chunk_records(self) -> list[dict[str, Any]]:
        q = select(t.svtg_chunks.c.chunk_id, t.svtg_chunks.c.page, t.svtg_chunks.c.printed_page,
                   t.svtg_chunks.c.section, t.svtg_chunks.c.text).order_by(t.svtg_chunks.c.ord)
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q).all()]

    def chunk_count(self) -> int:
        with self.engine.connect() as c:
            return int(c.execute(select(func.count()).select_from(t.svtg_chunks)).scalar_one())

    def svtg_source(self) -> dict[str, Any] | None:
        raw = self.get_meta("svtg_source")
        return json.loads(raw) if raw else None

    # ---------- saved settings ----------
    def settings_overrides(self) -> dict[str, Any]:
        with self.engine.connect() as c:
            return {k: v for k, v in c.execute(select(t.app_settings.c.key, t.app_settings.c.value)).all()}

    def replace_settings_overrides(self, values: dict[str, Any]) -> None:
        with self._tx() as c:
            c.execute(delete(t.app_settings))
            if values:
                c.execute(t.app_settings.insert(), [{"key": k, "value": v} for k, v in values.items()])

    # ---------- rate limit ----------
    def rate_hit(self, ip: str, minute: int) -> int:
        """Count one request from `ip` in this epoch minute; returns the count so far."""
        with self._tx() as c:
            stmt = self._insert(t.rate_limits).values(ip=ip, minute=minute, hits=1)
            hits = c.execute(stmt.on_conflict_do_update(index_elements=["ip", "minute"],
                                                        set_={"hits": t.rate_limits.c.hits + 1})
                             .returning(t.rate_limits.c.hits)).scalar_one()
            if random.random() < 0.01:  # prune old windows now and then
                c.execute(delete(t.rate_limits).where(t.rate_limits.c.minute < minute - 2))
        return int(hits)

    # ---------- access-code lockout ----------
    def add_failure(self, ip: str, ts: float) -> None:
        with self._tx() as c:
            c.execute(t.auth_failures.insert().values(ip=ip, ts=ts))

    def count_failures(self, ip: str, since: float) -> int:
        with self.engine.connect() as c:
            return int(c.execute(select(func.count()).select_from(t.auth_failures)
                                 .where(t.auth_failures.c.ip == ip, t.auth_failures.c.ts >= since)).scalar_one())

    def clear_failures(self, ip: str, keep_lockout: bool = False) -> None:
        with self._tx() as c:
            c.execute(delete(t.auth_failures).where(t.auth_failures.c.ip == ip))
            if not keep_lockout:
                c.execute(delete(t.auth_lockouts).where(t.auth_lockouts.c.ip == ip))

    def prune_failures(self, before: float) -> None:
        with self._tx() as c:
            c.execute(delete(t.auth_failures).where(t.auth_failures.c.ts < before))
            c.execute(delete(t.auth_lockouts).where(t.auth_lockouts.c.locked_until < before))

    def set_lockout(self, ip: str, until: float) -> None:
        with self._tx() as c:
            stmt = self._insert(t.auth_lockouts).values(ip=ip, locked_until=until)
            c.execute(stmt.on_conflict_do_update(index_elements=["ip"], set_={"locked_until": stmt.excluded.locked_until}))

    def locked_until(self, ips: list[str]) -> float:
        with self.engine.connect() as c:
            v = c.execute(select(func.max(t.auth_lockouts.c.locked_until)).where(t.auth_lockouts.c.ip.in_(ips))).scalar_one()
        return float(v or 0.0)

    def reset_limits(self) -> None:
        with self._tx() as c:
            for table in (t.rate_limits, t.auth_failures, t.auth_lockouts):
                c.execute(delete(table))

    # ---------- health ----------
    def ping(self) -> bool:
        try:
            with self.engine.connect() as c:
                c.execute(select(1)).scalar_one()
            return True
        except SQLAlchemyError:
            return False


def _run_dict(row) -> dict[str, Any]:
    d = dict(row)
    d["interview"] = bool(d["interview"])
    d["force"] = bool(d.get("force", False))
    d["conditions"] = list(d["conditions"])
    d["case_ids"] = list(d["case_ids"])
    return d


def _result_dict(row) -> dict[str, Any]:
    d = dict(row)
    d["interview"] = bool(d["interview"])
    d["cached"] = bool(d["cached"])
    return d


_default: dict[str, Store] = {}
_default_lock = threading.Lock()


def get_store() -> Store:
    """The app-wide store for the configured DATABASE_URL."""
    url = database_url()
    with _default_lock:
        s = _default.get(url)
        if s is None:
            s = _default[url] = Store(url)
        return s


def reset_store_cache() -> None:
    with _default_lock:
        _default.clear()
