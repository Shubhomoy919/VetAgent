import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMError, LLMRequest, Message
from app.llm.demo import DemoProvider
from app.llm.factory import get_provider
from app.llm.openai_compatible import OpenAICompatibleProvider

KEY = "sk-secret-should-never-appear"


def req() -> LLMRequest:
    return LLMRequest(system="sys", messages=[Message("user", "hi")])


def test_openai_compatible_success(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers)
        return httpx.Response(
            200,
            json={"model": "m-1", "choices": [{"message": {"content": '{"ok": 1}'}}],
                  "usage": {"prompt_tokens": 12, "completion_tokens": 3}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    p = OpenAICompatibleProvider("https://api.example.com/v1/", KEY, "m-1")
    r = p.complete(req())
    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["json"]["temperature"] == 0.0
    assert seen["json"]["messages"][0] == {"role": "system", "content": "sys"}
    assert seen["json"]["response_format"] == {"type": "json_object"}
    assert (r.text, r.tokens_in, r.tokens_out, r.tokens_estimated) == ('{"ok": 1}', 12, 3, False)


def test_openai_compatible_http_error_hides_key(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(401, text="invalid api key"))
    p = OpenAICompatibleProvider("https://api.example.com/v1", KEY, "m-1")
    with pytest.raises(LLMError) as e:
        p.complete(req())
    assert "401" in str(e.value)
    assert KEY not in str(e.value)


def test_openai_compatible_network_error(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(LLMError, match="ConnectError"):
        OpenAICompatibleProvider("http://localhost:1", KEY, "m").complete(req())


def test_openai_compatible_empty_or_malformed(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, json={"choices": []}))
    with pytest.raises(LLMError, match="Unexpected response shape"):
        OpenAICompatibleProvider("http://x", KEY, "m").complete(req())
    monkeypatch.setattr(httpx, "post", lambda *a, **k: httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}))
    with pytest.raises(LLMError, match="empty"):
        OpenAICompatibleProvider("http://x", KEY, "m").complete(req())


def test_factory_falls_back_to_demo_without_key():
    p = get_provider(Settings(_env_file=None, llm_provider="gemini", gemini_api_key=""))
    assert isinstance(p, DemoProvider)


def test_factory_openai_compatible():
    s = Settings(_env_file=None, llm_provider="openai_compatible", openai_api_key=KEY,
                 openai_base_url="http://x/v1", openai_model="m")
    p = get_provider(s)
    assert isinstance(p, OpenAICompatibleProvider) and p.model == "m"


# ---------- Gemini rate limits ----------

from google.genai import errors as genai_errors  # noqa: E402

from app.llm.gemini import GeminiProvider, quota_info  # noqa: E402


def _quota_body(quota_id: str, delay: str | None = "7s") -> dict:
    details = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]}]
    if delay:
        details.append({"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay})
    return {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota", "details": details}}


class _Resp:
    text = '{"ok": true}'
    candidates = None

    class usage_metadata:  # noqa: N801
        prompt_token_count = 10
        candidates_token_count = 3
        thoughts_token_count = 0


def _provider(responses, sleeps):
    p = GeminiProvider(KEY, "gemini-test", sleep=sleeps.append)
    seq = list(responses)

    def call(contents, config):
        nxt = seq.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    p._call = call  # type: ignore[method-assign]
    return p


def test_quota_info_parses_ids_and_delay():
    ids, delay = quota_info(_quota_body("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "34.5s"))
    assert ids == ["GenerateRequestsPerMinutePerProjectPerModel-FreeTier"] and delay == 34.5
    assert quota_info({"nothing": 1}) == ([], None)


def test_per_minute_429_waits_and_retries():
    err = genai_errors.ClientError(429, _quota_body("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "7s"))
    sleeps: list[float] = []
    r = _provider([err, err, _Resp()], sleeps).complete(req())
    assert r.text == '{"ok": true}'
    assert sleeps == [7.0, 7.0]


def test_per_minute_429_gives_up_after_retries():
    err = genai_errors.ClientError(429, _quota_body("GenerateRequestsPerMinutePerProjectPerModel-FreeTier", "500s"))
    sleeps: list[float] = []
    with pytest.raises(LLMError, match="still hit after 3 retries"):
        _provider([err] * 4, sleeps).complete(req())
    assert sleeps == [65.0, 65.0, 65.0]  # capped


def test_daily_quota_fails_fast():
    err = genai_errors.ClientError(429, _quota_body("GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
    sleeps: list[float] = []
    with pytest.raises(LLMError, match="daily quota exhausted.*PerDay"):
        _provider([err], sleeps).complete(req())
    assert sleeps == []


def test_server_error_retried_then_raised():
    err = genai_errors.ServerError(503, {"error": {"code": 503, "status": "UNAVAILABLE", "message": "overloaded"}})
    sleeps: list[float] = []
    assert _provider([err, _Resp()], sleeps).complete(req()).text == '{"ok": true}'
    with pytest.raises(LLMError, match="503"):
        _provider([err, err, err], []).complete(req())


class _Malformed:
    text = ""

    class _Cand:
        finish_reason = "FinishReason.MALFORMED_FUNCTION_CALL"

    candidates = [_Cand()]
    usage_metadata = None


def test_malformed_empty_response_is_retried():
    assert _provider([_Malformed(), _Resp()], []).complete(req()).text == '{"ok": true}'


def test_malformed_falls_back_to_plain_text_then_gives_up():
    seen = []
    p = _provider([_Malformed()] * 3 + [_Resp()], [])
    original = p._call

    def spy(contents, config):
        seen.append(config.response_mime_type)
        return original(contents, config)

    p._call = spy  # type: ignore[method-assign]
    assert p.complete(req()).text == '{"ok": true}'
    assert seen == ["application/json"] * 3 + ["text/plain"]
    with pytest.raises(LLMError, match="MALFORMED_FUNCTION_CALL"):
        _provider([_Malformed()] * 4, []).complete(req())


class _EmptyStop(_Malformed):
    class _Cand:
        finish_reason = "FinishReason.STOP"

    candidates = [_Cand()]


def test_empty_stop_response_is_retried():
    assert _provider([_EmptyStop(), _Resp()], []).complete(req()).text == '{"ok": true}'
