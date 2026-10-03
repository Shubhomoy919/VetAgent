"""The app-wide SVTG index, built from the configured PDF."""

from app.config import DATA_DIR, Settings
from app.data.loaders import DataError, load_drugs
from app.retrieval.search import SearchIndex, get_index

CACHE_DIR = DATA_DIR / "cache"


def drug_keywords() -> list[str]:
    try:
        return sorted({row.drug for row in load_drugs()})
    except DataError:
        return []


def svtg_index(settings: Settings) -> SearchIndex:
    return get_index(settings.pdf_path, CACHE_DIR, drug_keywords())
