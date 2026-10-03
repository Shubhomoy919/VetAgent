"""Step-by-step trace of a condition run (streamed to the UI in M4)."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

StepKind = Literal["llm", "tool", "owner", "retry", "verify", "rule", "cache"]


@dataclass
class Step:
    index: int
    kind: StepKind
    name: str
    input: Any = None
    output: Any = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Trace:
    on_step: Callable[[Step], None] | None = None
    steps: list[Step] = field(default_factory=list)

    def add(self, kind: StepKind, name: str, **kw: Any) -> Step:
        step = Step(index=len(self.steps) + 1, kind=kind, name=name, **kw)
        self.steps.append(step)
        if self.on_step:
            self.on_step(step)
        return step

    @property
    def tokens_in(self) -> int:
        return sum(s.tokens_in for s in self.steps)

    @property
    def tokens_out(self) -> int:
        return sum(s.tokens_out for s in self.steps)

    @property
    def tool_calls(self) -> int:
        return sum(1 for s in self.steps if s.kind in ("tool", "owner"))


def clip(text: str, n: int = 4000) -> str:
    return text if len(text) <= n else text[:n] + f"… [{len(text) - n} more chars]"
