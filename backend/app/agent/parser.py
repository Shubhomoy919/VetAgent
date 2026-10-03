"""Robust JSON extraction from model output.

Handles code fences, leading/trailing prose and nested braces inside strings.
Errors are raised as ParseError with a message that says what went wrong.
"""

import json
import re
from typing import Any

from pydantic import ValidationError

from app.agent.schema import FinalAnswer

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)


class ParseError(Exception):
    pass


def strip_fences(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def _first_object(text: str) -> str | None:
    """Return the first balanced {...} block, respecting JSON strings."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def extract_json(text: str) -> dict[str, Any]:
    if not text or not text.strip():
        raise ParseError("empty response")
    body = strip_fences(text)
    try:
        value = json.loads(body)
    except ValueError:
        block = _first_object(body)
        if block is None:
            raise ParseError(f"no JSON object found in response: {text[:120]!r}") from None
        try:
            value = json.loads(block)
        except ValueError as e:
            raise ParseError(f"invalid JSON: {e}") from None
    if not isinstance(value, dict):
        raise ParseError(f"expected a JSON object, got {type(value).__name__}")
    return value


def format_validation(err: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(x) for x in e['loc']) or '(root)'}: {e['msg']}" for e in err.errors()
    )


def parse_final_answer(data: dict[str, Any] | str) -> FinalAnswer:
    obj = extract_json(data) if isinstance(data, str) else data
    # Some models wrap the answer: {"final_answer": {...}} or {"answer": {...}}
    for key in ("final_answer", "answer", "revised_answer"):
        if isinstance(obj.get(key), dict) and "most_likely" not in obj:
            obj = obj[key]
            break
    try:
        return FinalAnswer.model_validate(obj)
    except ValidationError as e:
        raise ParseError(f"answer does not match the schema: {format_validation(e)}") from None


def parse_action(text: str) -> dict[str, Any]:
    """A ReAct step: {"thought", "action", "action_input"} or {"thought", "final_answer"}."""
    obj = extract_json(text)
    # Some models return the answer object itself instead of {"final_answer": {...}}.
    if "action" not in obj and "final_answer" not in obj and "most_likely" in obj:
        return {"thought": "", "final_answer": obj, "unwrapped": True}
    if "final_answer" in obj:
        if not isinstance(obj["final_answer"], dict):
            raise ParseError("final_answer must be a JSON object")
        return obj
    action = obj.get("action")
    if not isinstance(action, str) or not action.strip():
        raise ParseError('step must contain "action" (tool name) or "final_answer"')
    args = obj.get("action_input", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ParseError('"action_input" must be a JSON object')
    obj["action"] = action.strip()
    obj["action_input"] = args
    return obj
