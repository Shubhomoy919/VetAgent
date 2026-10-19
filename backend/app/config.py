"""Application settings from environment variables (and the repo-root .env file locally).

Keys are held only in memory. Nothing in this module logs or returns them;
callers should use `key_present` / `effective_provider` instead.
"""

import os
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
# Seed data (cases.json, drug_table.csv), the local SQLite database and the local SVTG PDF. Production keeps all
# state in Postgres and never writes here.
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

    # Local copy of the SVTG PDF, read only by the seed script (app.scripts.seed). Never deployed or served.
    svtg_pdf_path: str = "data/StandardVeterinaryTreatment.pdf"

    # Postgres in production (pooled URL); empty = local SQLite (data/vetagentbench.db).
    database_url: str = Field(default="", repr=False)
    # Direct (non-pooled) connection for migrations and the seed script; falls back to DATABASE_URL.
    database_url_unpooled: str = Field(default="", repr=False)

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
    max_body_bytes: int = Field(default=2_000_000, ge=10_000, le=4_000_000)
    # One run step (one case through one condition) must finish inside the platform's function limit
    # (Vercel Hobby: maxDuration 300 s). A step still running at this deadline is stored as "timeout".
    step_deadline_s: int = Field(default=240, ge=1, le=780)
    # A run with no new result for this long is treated as abandoned (closed browser) and marked interrupted.
    run_stale_s: int = Field(default=600, ge=60, le=86_400)
    # Frozen results snapshot (path relative to the repo root), loaded by the seed script; locally also loaded
    # into an empty database at start-up.
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
        # "data/x.pdf" resolves inside DATA_DIR.
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
        values = (self.gemini_api_key, self.openai_api_key, self.admin_access_code, self.session_secret, self.database_url,
                  self.database_url_unpooled)
        return [v for v in values if v.strip()]


_env: list[Settings] = []


def env_settings() -> Settings:
    """Settings from the environment only (no saved overrides): used where the database is not available yet."""
    if not _env:
        _env.append(Settings())
    return _env[0]


def configured_database_url() -> str:
    return env_settings().database_url


# Non-secret settings editable from the Settings page. Saved in the database (table app_settings); they override
# environment variables. API keys are deliberately not in this list: they live only in the environment.
EDITABLE_FIELDS = (
    "llm_provider",
    "gemini_model",
    "openai_base_url",
    "openai_model",
    "temperature",
    "max_steps",
    "max_owner_questions",
    "demo_delay_ms",
    "price_input_per_mtok",
    "price_output_per_mtok",
)


def load_overrides() -> dict[str, object]:
    """Saved settings from the database. An unreachable or empty database means no overrides."""
    try:
        from app.storage.db import get_store

        raw = get_store().settings_overrides()
    except Exception:
        return {}
    return {k: v for k, v in raw.items() if k in EDITABLE_FIELDS}


# Saved settings are re-read at most this often, so a change made on one serverless instance reaches the others.
SETTINGS_TTL_S = 10.0
_settings_lock = threading.Lock()
_settings_cache: dict[str, object] = {}


def get_settings() -> Settings:
    with _settings_lock:
        cached = _settings_cache.get("value")
        if isinstance(cached, Settings) and time.monotonic() - float(_settings_cache["at"]) < SETTINGS_TTL_S:  # type: ignore[arg-type]
            return cached
    value = Settings(**load_overrides())  # type: ignore[arg-type]
    with _settings_lock:
        _settings_cache.update(value=value, at=time.monotonic())
    return value


def reset_settings_cache() -> None:
    with _settings_lock:
        _settings_cache.clear()
        _env.clear()
