"""Runs on serverless functions: one request per step.

A run is created first (POST /api/runs). The browser then asks for each step in turn, one case through one
condition per request (POST /api/runs/{id}/step), so every request finishes well inside the platform's function
time limit. All state lives in the database: the run row, its results and traces, the answer cache and today's
token budget. A step that is still working at STEP_DEADLINE_S is stored as "timeout" and can be retried. A run
with no progress for RUN_STALE_S (closed browser) is marked interrupted.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.conditions import CONDITIONS, INTERVIEW_CONDITIONS
from app.agent.prompts import PROMPT_VERSION
from app.agent.runner import run_one
from app.agent.trace import Step
from app.config import Settings
from app.data.benchmark import benchmark_info
from app.data.loaders import load_cases, load_drugs
from app.data.models import Case
from app.llm.base import Provider
from app.llm.factory import get_provider
from app.retrieval.service import svtg_index
from app.scoring.verdict import judge
from app.security import redact
from app.storage.db import Store, get_store, utc_day


class RunConflict(Exception):
    pass


class BudgetExceeded(Exception):
    """The daily token cap (MAX_DAILY_TOKENS) is reached; no new runs until 00:00 UTC."""


class StepError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class StepCancelled(Exception):
    """The client went away or the deadline passed: stop at the next agent step."""


def budget_message(used: int, cap: int) -> str:
    return (f"Daily token budget reached ({used:,} of {cap:,} tokens used today). "
            "Runs are paused until 00:00 UTC. Stored results remain available.")


def timeout_message(seconds: int) -> str:
    return (f"Timed out: this condition did not finish within {seconds} s (the per-request limit). "
            "Nothing was stored for it except this note. Retry the condition.")


def result_payload(r: dict[str, Any], case: Case | None, result_id: int | None = None) -> dict[str, Any]:
    return {
        "id": result_id,
        "case_id": r["case_id"],
        "condition": r["condition"],
        "interview": r["interview"],
        "status": r["status"],
        "answer": r["answer"],
        "error": r["error"],
        "rules_fired": r.get("rules_fired", []),
        "owner_questions": r.get("owner_questions", []),
        "steps": r.get("steps", 0),
        "tokens_in": r.get("tokens_in", 0),
        "tokens_out": r.get("tokens_out", 0),
        "cost_usd": r.get("cost_usd"),
        "latency_ms": r.get("latency_ms", 0),
        "cached": r.get("cached", False),
        "verdict": judge(r["answer"], case) if case else {"scored": False, "stamps": []},
    }


def summary(run: dict[str, Any], done: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    out = {
        "run_id": run["id"], "status": run["status"], "n_done": run["n_done"], "n_total": run["n_total"],
        "case_ids": run["case_ids"], "conditions": run["conditions"], "interview": run["interview"],
        "force": run["force"], "provider": run["provider"], "model": run["model"],
    }
    if done is not None:
        out["done"] = [{"case_id": d["case_id"], "condition": d["condition"]} for d in done]
    return out


@dataclass
class StepContext:
    run: dict[str, Any]
    case: Case
    condition: str
    provider: Provider


class RunManager:
    def __init__(self, store: Store | None = None):
        self._store = store

    @property
    def store(self) -> Store:
        return self._store or get_store()

    # ---------- budget ----------
    def budget(self, settings: Settings) -> dict[str, Any]:
        cap = settings.max_daily_tokens
        used = self.store.tokens_on(utc_day())
        return {"cap": cap, "used": used, "remaining": None if cap == 0 else max(0, cap - used),
                "exhausted": cap > 0 and used >= cap}

    def _provider(self, settings: Settings) -> Provider:
        provider = get_provider(settings)
        if settings.is_production and provider.name == "demo":
            raise ValueError("No live model is configured on this server, so runs are disabled. Stored results remain available.")
        return provider

    # ---------- runs ----------
    def start(self, settings: Settings, case_ids: list[str], conditions: list[str] | None, interview: bool,
              force: bool, label: str = "bench") -> dict[str, Any]:
        cases = {c.case_id: c for c in load_cases()}
        missing = [c for c in case_ids if c not in cases]
        if missing:
            raise ValueError(f"Unknown case id(s): {', '.join(missing)}")
        if not case_ids:
            raise ValueError("No cases selected")
        if len(case_ids) > settings.max_cases_per_run:
            raise ValueError(f"Too many cases for one run ({len(case_ids)}); the limit is {settings.max_cases_per_run}.")
        if len(set(case_ids)) != len(case_ids):
            raise ValueError("Each case can appear only once in a run")
        allowed = INTERVIEW_CONDITIONS if interview else CONDITIONS
        conds = list(conditions) if conditions else list(allowed)
        bad = [c for c in conds if c not in allowed]
        if bad:
            raise ValueError(f"Condition(s) {', '.join(bad)} not available in {'interview' if interview else 'standard'} mode")

        provider = self._provider(settings)
        b = self.budget(settings)
        if b["exhausted"]:
            raise BudgetExceeded(budget_message(b["used"], b["cap"]))
        self.store.expire_stale_runs(settings.run_stale_s)
        active = self.store.active_run(settings.run_stale_s)
        if active:
            raise RunConflict(f"Run {active['id']} is still running. Wait for it to finish or cancel it.")
        bench = benchmark_info()
        run_id = self.store.create_run(
            provider=provider.name, model=provider.model, prompt_version=PROMPT_VERSION, conditions=conds,
            case_ids=case_ids, interview=interview, label=label, temperature=settings.temperature,
            benchmark_version=bench["version"], benchmark_hash=bench["hash"], force=force,
        )
        run = self.store.get_run(run_id)
        assert run is not None
        return summary(run, [])

    def active(self, settings: Settings) -> dict[str, Any] | None:
        self.store.expire_stale_runs(settings.run_stale_s)
        run = self.store.active_run(settings.run_stale_s)
        return summary(run, self.store.done_keys(run["id"])) if run else None

    def finish(self, run_id: str, status: str | None = None) -> dict[str, Any]:
        """Close a run: `status` given (cancelled), or done / done_with_errors from its results. Idempotent."""
        run = self.store.get_run(run_id)
        if run is None:
            raise StepError(404, f"No run {run_id}")
        if run["status"] == "running":
            if status is None:
                done = self.store.done_keys(run_id)
                status = "done" if all(d["status"] == "ok" for d in done) and len(done) >= run["n_total"] else "done_with_errors"
            self.store.finish_run(run_id, status)
            run = self.store.get_run(run_id) or run
        return summary(run, self.store.done_keys(run_id))

    def cancel(self, run_id: str) -> bool:
        run = self.store.get_run(run_id)
        if not run or run["status"] != "running":
            return False
        self.store.finish_run(run_id, "cancelled")
        return True

    # ---------- one step ----------
    def prepare_step(self, settings: Settings, run_id: str, case_id: str, condition: str) -> StepContext:
        """Check a step before it starts streaming; raises StepError with an HTTP status and a message."""
        run = self.store.get_run(run_id)
        if run is None:
            raise StepError(404, f"No run {run_id}")
        if run["status"] != "running":
            raise StepError(409, f"Run {run_id} is {run['status'].replace('_', ' ')}; start a new run.")
        if case_id not in run["case_ids"] or condition not in run["conditions"]:
            raise StepError(400, f"{case_id} · {condition} is not part of run {run_id}")
        if any(d["case_id"] == case_id and d["condition"] == condition for d in self.store.done_keys(run_id)):
            raise StepError(409, f"{case_id} · {condition} already has a result in run {run_id}")
        case = next((c for c in load_cases() if c.case_id == case_id), None)
        if case is None:
            raise StepError(400, f"Case {case_id} no longer exists")
        try:
            provider = self._provider(settings)
        except ValueError as e:
            raise StepError(400, str(e)) from e
        if (provider.name, provider.model) != (run["provider"], run["model"]):
            raise StepError(409, f"The model changed since this run started ({run['model']} → {provider.model}); start a new run.")
        b = self.budget(settings)
        if b["exhausted"]:
            self.store.finish_run(run_id, "budget_exhausted")
            raise StepError(429, budget_message(b["used"], b["cap"]))
        return StepContext(run=run, case=case, condition=condition, provider=provider)

    def run_step(self, settings: Settings, ctx: StepContext, emit: Callable[[str, dict[str, Any]], None],
                 cancel: threading.Event | None = None) -> dict[str, Any]:
        """Run one case through one condition and store the result. Emits result_started, step… and
        result_done (plus run_error when the run has to stop). Returns the result_done data."""
        run, case = ctx.run, ctx.case
        cancel = cancel or threading.Event()
        key = {"case_id": case.case_id, "condition": ctx.condition, "interview": run["interview"]}
        emit("result_started", key)
        steps: list[dict[str, Any]] = []

        def on_step(step: Step) -> None:
            if cancel.is_set():
                raise StepCancelled()
            d = step.to_dict()
            steps.append(d)
            emit("step", {**key, "step": d})

        box: dict[str, Any] = {}

        def work() -> None:
            try:
                box["r"] = run_one(case=case, condition=ctx.condition, provider=ctx.provider,  # type: ignore[arg-type]
                                   settings=settings, index=svtg_index(settings), drugs=load_drugs(),
                                   store=self.store, interview=run["interview"], force=run["force"], on_step=on_step)
            except BaseException as e:  # noqa: BLE001 - reported to the caller below
                box["exc"] = e

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(settings.step_deadline_s)
        if worker.is_alive():
            cancel.set()  # the worker stops at its next agent step and stores nothing
            r: dict[str, Any] = {**key, "status": "timeout", "answer": None, "error": timeout_message(settings.step_deadline_s),
                                 "trace": steps, "rules_fired": [], "owner_questions": [], "steps": 0, "tokens_in": 0,
                                 "tokens_out": 0, "cost_usd": None, "latency_ms": settings.step_deadline_s * 1000,
                                 "cached": False, "cache_key": None}
        elif "exc" in box:
            raise box["exc"]
        else:
            r = box["r"]
        if r.get("error"):
            r["error"] = redact(r["error"], settings)

        rid = self.store.add_result(run["id"], r)
        fresh = self.store.get_run(run["id"]) or run
        payload = result_payload(r, case, rid)
        payload["trace"] = r["trace"]
        stop = None
        if r.get("quota_exhausted"):
            stop = "quota"
            self.store.finish_run(run["id"], "quota_exhausted")
            emit("run_error", {"error": f"{r['error']} The run was stopped; finished results are kept."})
        else:
            b = self.budget(settings)
            if b["exhausted"] and fresh["n_done"] < fresh["n_total"]:
                stop = "budget"
                self.store.finish_run(run["id"], "budget_exhausted")
                emit("run_error", {"error": budget_message(b["used"], b["cap"]) + " This run was stopped; finished results are kept."})
            elif fresh["n_done"] >= fresh["n_total"]:
                self.finish(run["id"])
        done = {**key, "result": payload, "n_done": fresh["n_done"], "n_total": fresh["n_total"], "stop": stop}
        emit("result_done", done)
        return done


manager = RunManager()
