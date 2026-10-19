"""Application settings, loaded from the repo-root .env file.

Keys are held only in memory. Nothing in this module logs or returns them;
callers should use `key_present` / `effective_provider` instead.
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# Writable data (cases, drug table, runs.db, SVTG index cache). In Docker this is the persistent volume.
DATA_DIR = Path(os.environ.get("DATA_DIR") or REPO_ROOT / "data").resolve()

Provider = Literal["gemini", "openai_compatible", "demo"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # "PRICE_INPUT_PER_MTOK=" in .env means "not set"
    )

    llm_provider: Provider = "demo"

    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"

    openai_base_url: str = ""
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = ""

    svtg_pdf_path: str = "data/StandardVeterinaryTreatment.pdf"

    # Deployment. In production, demo runs are refused and hidden, API docs are off, and an access code is
    # always required for runs, edits, Review and Settings (with no ADMIN_ACCESS_CODE set, nobody can unlock).
    app_env: Literal["development", "production"] = "development"
    admin_access_code: str = Field(default="", repr=False)
    session_secret: str = Field(default="", repr=False)
    session_hours: int = Field(default=12, ge=1, le=168)
    # Secure cookies need HTTPS. Defaults to on in production; set COOKIE_SECURE=false only for local http tests.
    cookie_secure: bool | None = None
    # Comma-separated origins allowed for cross-origin requests and unsafe methods, e.g. https://vab.example.org
    allowed_origins: str = ""
    rate_limit_per_minute: int = Field(default=240, ge=10, le=10_000)
    auth_max_attempts: int = Field(default=5, ge=1, le=50)
    auth_lockout_minutes: int = Field(default=15, ge=1, le=1440)
    # Hard cap on live-model tokens (in + out) per UTC day across all runs; 0 = no cap (development only).
    max_daily_tokens: int = Field(default=1_000_000, ge=0)
    max_cases_per_run: int = Field(default=30, ge=1, le=500)
    max_body_bytes: int = Field(default=2_000_000, ge=10_000, le=50_000_000)
    # Frozen results snapshot, loaded into an empty database at startup (path relative to the repo root).
    snapshot_path: str = "snapshots/v1.0.0/run.json"
    autoload_snapshot: bool = True

    # Agent
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_steps: int = Field(default=6, ge=1, le=12)
    max_owner_questions: int = Field(default=5, ge=1, le=10)
    # Demo provider only: pause per call so streamed steps are visible in demos.
    demo_delay_ms: int = Field(default=0, ge=0, le=5000)

    # Optional pricing (USD per million tokens). Left empty, cost is reported as unknown.
    price_input_per_mtok: float | None = None
    price_output_per_mtok: float | None = None

    def cost_usd(self, tokens_in: int, tokens_out: int) -> float | None:
        if self.effective_provider == "demo":
            return 0.0
        if self.price_input_per_mtok is None or self.price_output_per_mtok is None:
            return None
        return round(tokens_in / 1e6 * self.price_input_per_mtok + tokens_out / 1e6 * self.price_output_per_mtok, 6)

    @property
    def key_present(self) -> bool:
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key.strip())
        if self.llm_provider == "openai_compatible":
            return bool(self.openai_api_key.strip() and self.openai_base_url.strip())
        return False

    @property
    def effective_provider(self) -> Provider:
        """The provider actually used: falls back to demo when no key is configured."""
        return self.llm_provider if self.key_present else "demo"

    @property
    def model_id(self) -> str:
        provider = self.effective_provider
        if provider == "gemini":
            return self.gemini_model
        if provider == "openai_compatible":
            return self.openai_model or "unset"
        return "demo"

    @property
    def pdf_path(self) -> Path:
        path = Path(self.svtg_pdf_path)
        if path.is_absolute():
            return path
        # "data/x.pdf" resolves inside DATA_DIR, so the same setting works locally and on a Docker volume.
        if path.parts and path.parts[0] == "data":
            return DATA_DIR.joinpath(*path.parts[1:])
        return REPO_ROOT / path

    @property
    def snapshot_file(self) -> Path:
        path = Path(self.snapshot_path)
        return path if path.is_absolute() else REPO_ROOT / path

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_production if self.cookie_secure is None else self.cookie_secure

    @property
    def access_required(self) -> bool:
        """Production always needs the code; development only when one is configured."""
        return self.is_production or bool(self.admin_access_code.strip())

    @property
    def origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def secrets(self) -> list[str]:
        """Values that must never appear in logs or responses."""
        return [v for v in (self.gemini_api_key, self.openai_api_key, self.admin_access_code, self.session_secret) if v.strip()]


# Non-secret settings editable from the Settings page. Saved to data/settings.json (gitignored); they override
# .env. API keys are deliberately not in this list: they live only in .env.
OVERRIDES_PATH = DATA_DIR / "settings.json"
EDITABLE_FIELDS = (
    "llm_provider",
    "gemini_model",
    "openai_base_url",
    "openai_model",
    "svtg_pdf_path",
    "temperature",
    "max_steps",
    "max_owner_questions",
    "demo_delay_ms",
    "price_input_per_mtok",
    "price_output_per_mtok",
)


def load_overrides(path: Path | None = None) -> dict[str, object]:
    path = path or OVERRIDES_PATH
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if k in EDITABLE_FIELDS} if isinstance(raw, dict) else {}


@lru_cache
def get_settings() -> Settings:
    return Settings(**load_overrides())  # type: ignore[arg-type]


def reset_settings_cache() -> None:
    get_settings.cache_clear()
