"""Keep tests hermetic: never read the developer's .env or data/settings.json.

Without this, a real API key in .env would switch tests to live mode and spend quota.
"""

import pytest

from app import config, security


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    monkeypatch.setattr(config, "OVERRIDES_PATH", tmp_path / "no-settings.json")
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_MODEL", "OPENAI_MODEL",
                "APP_ENV", "ADMIN_ACCESS_CODE", "SESSION_SECRET", "ALLOWED_ORIGINS", "RATE_LIMIT_PER_MINUTE",
                "MAX_DAILY_TOKENS", "MAX_CASES_PER_RUN", "MAX_BODY_BYTES"):
        monkeypatch.delenv(var, raising=False)
    config.reset_settings_cache()
    security.rate_limiter.reset()
    security.lockout.reset()
    yield
    config.reset_settings_cache()
