"""Keep tests hermetic: never read the developer's .env or data/settings.json.

Without this, a real API key in .env would switch tests to live mode and spend quota.
"""

import pytest

from app import config


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setitem(config.Settings.model_config, "env_file", None)
    monkeypatch.setattr(config, "OVERRIDES_PATH", tmp_path / "no-settings.json")
    for var in ("LLM_PROVIDER", "GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "GEMINI_MODEL", "OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)
    config.reset_settings_cache()
    yield
    config.reset_settings_cache()
