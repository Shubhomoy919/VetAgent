from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import REPO_ROOT, Settings, get_settings
from app.main import app

FAKE_KEY = "sk-test-DO-NOT-LEAK-0123456789"


def make_settings(**overrides) -> Settings:
    # _env_file=None: ignore the developer's real .env so tests are hermetic.
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def client_with():
    def _client(**overrides) -> TestClient:
        settings = make_settings(**overrides)
        app.dependency_overrides[get_settings] = lambda: settings
        return TestClient(app)

    yield _client
    app.dependency_overrides.clear()


def test_health_without_key_runs_in_demo_mode(client_with):
    res = client_with(llm_provider="gemini", gemini_api_key="").get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["key_present"] is False
    assert body["configured_provider"] == "gemini"
    assert body["provider"] == "demo"
    assert body["mode"] == "demo"
    assert body["model"] == "demo"


def test_health_reports_required_fields(client_with):
    body = client_with().get("/api/health").json()
    for field in ("pdf_loaded", "pages", "chunks", "key_present", "model", "counts"):
        assert field in body
    assert set(body["counts"]) == {"cases", "drugs", "runs"}


def test_health_with_key_never_exposes_it(client_with):
    res = client_with(
        llm_provider="gemini", gemini_api_key=FAKE_KEY, gemini_model="gemini-2.5-flash"
    ).get("/api/health")
    body = res.json()
    assert body["key_present"] is True
    assert body["mode"] == "live"
    assert body["model"] == "gemini-2.5-flash"
    assert FAKE_KEY not in res.text


def test_settings_repr_hides_keys():
    settings = make_settings(gemini_api_key=FAKE_KEY, openai_api_key=FAKE_KEY)
    assert FAKE_KEY not in repr(settings)


def test_openai_compatible_needs_key_and_base_url(client_with):
    body = client_with(llm_provider="openai_compatible", openai_api_key=FAKE_KEY).get(
        "/api/health"
    ).json()
    assert body["key_present"] is False
    assert body["mode"] == "demo"


def test_missing_pdf_reported_not_loaded(client_with, tmp_path: Path):
    body = client_with(svtg_pdf_path=str(tmp_path / "missing.pdf")).get("/api/health").json()
    assert body["pdf_loaded"] is False
    assert body["pages"] == 0


def test_svtg_pdf_opens():
    default_pdf = make_settings().pdf_path
    if not default_pdf.is_file():
        pytest.skip(f"SVTG PDF not present at {default_pdf.relative_to(REPO_ROOT)}")
    from app.api.health import pdf_status

    loaded, pages = pdf_status(default_pdf)
    assert loaded is True
    assert pages > 0
