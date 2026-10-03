"""Pick the provider from settings. No key → demo."""

from app.config import Settings
from app.llm.base import Provider
from app.llm.demo import DemoProvider


def get_provider(settings: Settings) -> Provider:
    provider = settings.effective_provider
    if provider == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    if provider == "openai_compatible":
        from app.llm.openai_compatible import OpenAICompatibleProvider

        return OpenAICompatibleProvider(settings.openai_base_url, settings.openai_api_key, settings.openai_model)
    return DemoProvider()
