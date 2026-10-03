"""Provider-neutral chat interface.

Every provider takes the same LLMRequest and returns an LLMResponse. `task` and
`context` describe what the agent is asking for; real providers ignore them,
the demo provider uses them to build sample responses without a model.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant"]
Task = Literal["answer", "react", "verify", "owner"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


@dataclass
class LLMRequest:
    system: str
    messages: list[Message]
    json_mode: bool = True
    task: Task = "answer"
    context: dict[str, Any] = field(default_factory=dict)
    temperature: float = 0.0


@dataclass(frozen=True)
class LLMResponse:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    model: str
    tokens_estimated: bool = False


class LLMError(Exception):
    """The provider call failed. The message is safe to show (never contains keys)."""


class QuotaExhausted(LLMError):
    """A quota that will not recover within the run (e.g. a daily limit). Runs stop at the first one."""


class Provider(Protocol):
    name: str
    model: str

    def complete(self, request: LLMRequest) -> LLMResponse: ...


def estimate_tokens(text: str) -> int:
    """Rough token count (≈4 characters per token) for providers that report none."""
    return max(1, len(text) // 4)
