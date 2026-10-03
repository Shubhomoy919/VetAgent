"""Google Gemini via the google-genai SDK.

Rate limits: on HTTP 429 the error's QuotaFailure / RetryInfo details are read. A per-minute limit is retried
after the delay Google asks for (up to MAX_RATE_RETRIES times); a per-day quota fails at once with a clear
message, since waiting a minute will not help. 5xx server errors get a short backoff retry.
"""

import re
import time
from typing import Any

from app.llm.base import LLMError, LLMRequest, LLMResponse, estimate_tokens

MAX_RATE_RETRIES = 3
MAX_SERVER_RETRIES = 2
MAX_WAIT_S = 65.0


def quota_info(details: Any) -> tuple[list[str], float | None]:
    """(quota ids, retry delay in seconds) from a Gemini error body."""
    ids: list[str] = []
    delay: float | None = None
    err = details.get("error", details) if isinstance(details, dict) else {}
    for d in err.get("details", []) if isinstance(err, dict) else []:
        if not isinstance(d, dict):
            continue
        kind = str(d.get("@type", ""))
        if kind.endswith("QuotaFailure"):
            ids += [str(v.get("quotaId", "")) for v in d.get("violations", []) if isinstance(v, dict) and v.get("quotaId")]
        elif kind.endswith("RetryInfo"):
            m = re.match(r"([0-9.]+)s", str(d.get("retryDelay", "")))
            if m:
                delay = float(m.group(1))
    return ids, delay


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_s: float = 120.0, sleep=time.sleep):
        from google import genai
        from google.genai import errors, types

        self._types = types
        self._errors = errors
        self._sleep = sleep
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )
        self.model = model

    def _call(self, contents, config):
        return self._client.models.generate_content(model=self.model, contents=contents, config=config)

    def complete(self, request: LLMRequest) -> LLMResponse:
        types = self._types
        contents = [
            types.Content(role="model" if m.role == "assistant" else "user", parts=[types.Part(text=m.content)])
            for m in request.messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=request.system,
            temperature=request.temperature,
            response_mime_type="application/json" if request.json_mode else "text/plain",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        start = time.perf_counter()
        rate_tries = server_tries = 0
        while True:
            try:
                resp = self._call(contents, config)
                break
            except self._errors.APIError as e:
                if e.code == 429:
                    ids, delay = quota_info(e.details)
                    daily = any("PerDay" in q for q in ids)
                    label = ", ".join(ids) or "rate limit"
                    if daily:
                        raise LLMError(
                            f"Gemini daily quota exhausted ({label}). Wait for the daily reset or enable billing; "
                            "retrying now will not help."
                        ) from None
                    if rate_tries >= MAX_RATE_RETRIES:
                        raise LLMError(f"Gemini rate limit still hit after {rate_tries} retries ({label}): {e.message}") from None
                    rate_tries += 1
                    self._sleep(min(delay if delay is not None else 10.0 * rate_tries, MAX_WAIT_S))
                    continue
                if e.code and e.code >= 500 and server_tries < MAX_SERVER_RETRIES:
                    server_tries += 1
                    self._sleep(2.0 * server_tries)
                    continue
                raise LLMError(f"Gemini error {e.code} {e.status}: {str(e.message)[:500]}") from None
            except Exception as e:  # network errors etc.; never echo request headers
                raise LLMError(f"Gemini call failed ({type(e).__name__}): {str(e)[:300]}") from None
        latency = int((time.perf_counter() - start) * 1000)

        text = resp.text or ""
        if not text.strip():
            reason = ""
            if resp.candidates and resp.candidates[0].finish_reason:
                reason = f" (finish_reason={resp.candidates[0].finish_reason})"
            raise LLMError(f"Gemini returned an empty response{reason}")

        usage = resp.usage_metadata
        tin = (usage.prompt_token_count or 0) if usage else 0
        tout = ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
        estimated = not usage or not tin
        return LLMResponse(
            text=text,
            tokens_in=tin or estimate_tokens(request.system + "".join(m.content for m in request.messages)),
            tokens_out=tout or estimate_tokens(text),
            latency_ms=latency,
            model=self.model,
            tokens_estimated=estimated,
        )
