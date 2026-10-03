"""Any OpenAI-compatible /chat/completions endpoint (OpenAI, Groq, Ollama, vLLM, ...)."""

import time

import httpx

from app.llm.base import LLMError, LLMRequest, LLMResponse, estimate_tokens


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 120.0):
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._timeout = timeout_s
        self.model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        messages = [{"role": "system", "content": request.system}] + [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        payload: dict = {"model": self.model, "messages": messages, "temperature": request.temperature}
        if request.json_mode:
            payload["response_format"] = {"type": "json_object"}

        start = time.perf_counter()
        try:
            r = httpx.post(self._url, json=payload, headers=self._headers, timeout=self._timeout)
        except httpx.HTTPError as e:
            raise LLMError(f"Request to {self._url} failed: {type(e).__name__}") from None
        latency = int((time.perf_counter() - start) * 1000)

        if r.status_code >= 400:
            raise LLMError(f"{self._url} returned HTTP {r.status_code}: {r.text[:300]}")
        try:
            body = r.json()
            text = body["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMError(f"Unexpected response shape from {self._url}: {e}") from None
        if not text.strip():
            raise LLMError("Model returned an empty response")

        usage = body.get("usage") or {}
        tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
        return LLMResponse(
            text=text,
            tokens_in=tin or estimate_tokens(request.system + "".join(m.content for m in request.messages)),
            tokens_out=tout or estimate_tokens(text),
            latency_ms=latency,
            model=body.get("model") or self.model,
            tokens_estimated=not (tin and tout),
        )
