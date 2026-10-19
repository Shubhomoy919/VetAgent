"""Background run execution with an event log for SSE streaming.

One run at a time. Each run keeps its full event list in memory, so a client
that connects (or reconnects) late replays everything from the start.
Cancellation is checked after every trace step and between results.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.agent.conditions import CONDITIONS, INTERVIEW_CONDITIONS
from app.agent.prompts import PROMPT_VERSION
from app.agent.runner import run_one
from app.agent.trace import Step
from app.config import Settings
from app.data.benchmark import benchmark_info
from app.data.loaders import load_cases, load_drugs
from app.llm.factory import get_provider
from app.retrieval.service import svtg_index
from app.scoring.verdict import judge
from app.security import redact
from app.storage.db import Store


class RunCancelled(Exception):
    pass


class RunConflict(Exception):
    pass


class QuotaStop(Exception):
    pass


class BudgetExceeded(Exception):
    """The daily token cap (MAX_DAILY_TOKENS) is reached; no new runs until 00:00 UTC."""


class BudgetStop(Exception):
    pass


def day_start_iso(now: datetime | None = None) -> str:
    t = now or datetime.now(UTC)
    return t.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="seconds")


def budget_message(used: int, cap: int) -> str:
    return (f"Daily token budget reached ({used:,} of {cap:,} tokens used today). "
            "Runs are paused until 00:00 UTC. Stored results remain available.")


@dataclass
class RunState:
    id: str
    case_ids: list[str]
    conditions: list[str]
    interview: bool
    force: bool
    provider: str
    model: str
    n_total: int
    n_done: int = 0
    status: str = "running"
    events: list[dict[str, Any]] = field(default_factory=list)
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    started_at: float = field(default_factory=time.time)
    closed: bool = False  # set only after the final run_done event is in the log

    def emit(self, type_: str, data: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({"id": len(self.events) + 1, "type": type_, "data": data})

    def events_since(self, n: int) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[n:]

    @property
    def finished(self) -> bool:
        return self.status != "running"

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.id, "status": self.status, "n_done": self.n_done, "n_total": self.n_total,
            "case_ids": self.case_ids, "conditions": self.conditions, "interview": self.interview,
            "force": self.force, "provider": self.provider, "model": self.model,
        }


def result_payload(r: dict[str, Any], case, result_id: int | None = None) -> dict[str, Any]:
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


class RunManager:
    def __init__(self, store: Store | None = None):
        self._store = store
        self._lock = threading.Lock()
        self._runs: dict[str, RunState] = {}
        self._active: RunState | None = None

    @property
    def store(self) -> Store:
        if self._store is None:
            self._store = Store()
        return self._store

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def active(self) -> RunState | None:
        a = self._active
        return a if a and not a.finished else None

    def budget(self, settings: Settings) -> dict[str, Any]:
        cap = settings.max_daily_tokens
        used = self.store.tokens_since(day_start_iso())
        return {"cap": cap, "used": used, "remaining": None if cap == 0 else max(0, cap - used),
                "exhausted": cap > 0 and used >= cap}

    def start(
        self, settings: Settings, case_ids: list[str], conditions: list[str] | None, interview: bool, force: bool,
        label: str = "bench",
    ) -> RunState:
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

        provider = get_provider(settings)
        if settings.is_production and provider.name == "demo":
            raise ValueError("No live model is configured on this server, so runs are disabled. Stored results remain available.")
        b = self.budget(settings)
        if b["exhausted"]:
            raise BudgetExceeded(budget_message(b["used"], b["cap"]))
        bench = benchmark_info()
        with self._lock:
            if self.active():
                raise RunConflict(f"Run {self._active.id} is still running")  # type: ignore[union-attr]
            run_id = self.store.create_run(
                provider=provider.name, model=provider.model, prompt_version=PROMPT_VERSION, conditions=conds,
                case_ids=case_ids, interview=interview, label=label, temperature=settings.temperature,
                benchmark_version=bench["version"], benchmark_hash=bench["hash"],
            )
            state = RunState(
                id=run_id, case_ids=case_ids, conditions=conds, interview=interview, force=force,
                provider=provider.name, model=provider.model, n_total=len(case_ids) * len(conds),
            )
            self._runs[run_id] = state
            self._active = state
            # keep memory bounded
            for old in list(self._runs)[:-20]:
                if self._runs[old].finished:
                    del self._runs[old]

        threading.Thread(target=self._work, args=(state, settings, provider, cases), daemon=True).start()
        return state

    def shutdown(self, timeout: float = 20.0) -> None:
        """Graceful stop: cancel the active run and wait for it to record its final status."""
        a = self.active()
        if a is None:
            return
        a.cancel.set()
        end = time.time() + timeout
        while not a.closed and time.time() < end:
            time.sleep(0.1)

    def cancel(self, run_id: str) -> bool:
        state = self._runs.get(run_id)
        if not state or state.finished:
            return False
        state.cancel.set()
        return True

    def _work(self, state: RunState, settings: Settings, provider, cases) -> None:
        state.emit("run_started", state.summary())
        status = "done"
        try:
            drugs = load_drugs()
            index = svtg_index(settings)
            for cid in state.case_ids:
                for cond in state.conditions:
                    if state.cancel.is_set():
                        raise RunCancelled()
                    key = {"case_id": cid, "condition": cond, "interview": state.interview}
                    state.emit("result_started", key)

                    def on_step(step: Step, key=key) -> None:
                        state.emit("step", {**key, "step": step.to_dict()})
                        if state.cancel.is_set():
                            raise RunCancelled()

                    r = run_one(case=cases[cid], condition=cond, provider=provider, settings=settings, index=index,
                                drugs=drugs, store=self.store, interview=state.interview, force=state.force,
                                on_step=on_step)
                    if r.get("error"):
                        r["error"] = redact(r["error"], settings)
                    rid = self.store.add_result(state.id, r)
                    state.n_done += 1
                    payload = result_payload(r, cases[cid], rid)
                    payload["trace"] = r["trace"]
                    state.emit("result_done", {**key, "result": payload, "n_done": state.n_done, "n_total": state.n_total})
                    if r.get("quota_exhausted"):
                        state.emit("run_error", {"error": r["error"] + " The run was stopped; finished results are kept."})
                        raise QuotaStop()
                    if r["status"] != "ok":
                        status = "done_with_errors"
                    b = self.budget(settings)
                    if b["exhausted"] and state.n_done < state.n_total:
                        state.emit("run_error", {"error": budget_message(b["used"], b["cap"]) + " This run was stopped; finished results are kept."})
                        raise BudgetStop()
        except RunCancelled:
            status = "cancelled"
        except QuotaStop:
            status = "quota_exhausted"
        except BudgetStop:
            status = "budget_exhausted"
        except Exception as e:  # unexpected: show the error class and message (redacted), never a traceback
            status = "failed"
            state.emit("run_error", {"error": redact(f"{type(e).__name__}: {e}", settings)})
        finally:
            self.store.finish_run(state.id, status)
            with state.lock:
                state.status = status
                state.events.append({"id": len(state.events) + 1, "type": "run_done", "data": state.summary()})
                state.closed = True


manager = RunManager()
