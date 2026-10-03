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
