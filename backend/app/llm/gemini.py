"""Google Gemini via the google-genai SDK."""

import time

from app.llm.base import LLMError, LLMRequest, LLMResponse, estimate_tokens


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_s: float = 120.0):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )
        self.model = model

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
        )
        start = time.perf_counter()
        try:
            resp = self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except Exception as e:  # SDK raises several error types; never echo request headers
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
