"""Application settings, loaded from the repo-root .env file.

Keys are held only in memory. Nothing in this module logs or returns them;
callers should use `key_present` / `effective_provider` instead.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

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
        return path if path.is_absolute() else REPO_ROOT / path


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
