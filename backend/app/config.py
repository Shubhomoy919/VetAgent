"""Application settings, loaded from the repo-root .env file.

Keys are held only in memory. Nothing in this module logs or returns them;
callers should use `key_present` / `effective_provider` instead.
"""

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
    )

    llm_provider: Provider = "demo"

    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = "gemini-2.5-flash"

    openai_base_url: str = ""
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = ""

    svtg_pdf_path: str = "data/StandardVeterinaryTreatment.pdf"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
