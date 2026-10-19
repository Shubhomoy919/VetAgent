"""The app-wide SVTG search index, built in memory from the passages stored in the database.

The seed script (app.scripts.seed) parses a local copy of the PDF and stores page-numbered passages in the
table svtg_chunks. Each server instance loads them once and rebuilds the BM25 index when they change. With no
passages stored, the index is empty: searches return nothing and /api/health reports index_loaded false.
"""

import threading
from typing import Any

from app.config import Settings
from app.data.loaders import DataError, load_drugs
from app.retrieval.ingest import Chunk
from app.retrieval.search import SearchIndex

_lock = threading.Lock()
_cache: dict[tuple[str, str, str], SearchIndex] = {}


def drug_keywords() -> list[str]:
    try:
        return sorted({row.drug for row in load_drugs()})
    except DataError:
        return []


def svtg_index(settings: Settings | None = None) -> SearchIndex:
    from app.storage.db import get_store

    try:
        store = get_store()
        key = (store.url, store.get_meta("chunks_rev") or "0", store.data_rev())
    except Exception:
        return SearchIndex([])
    with _lock:
        idx = _cache.get(key)
    if idx is not None:
        return idx
    try:
        chunks = [Chunk(**r) for r in store.chunk_records()]
    except Exception:
        return SearchIndex([])
    idx = SearchIndex(chunks, drug_keywords())
    with _lock:
        _cache.clear()
        _cache[key] = idx
    return idx


def index_status() -> dict[str, Any]:
    """index_loaded, chunk count and source page count, for health and Settings."""
    from app.storage.db import get_store

    try:
        store = get_store()
        n = store.chunk_count()
        source = store.svtg_source() or {}
    except Exception:
        return {"index_loaded": False, "chunks": 0, "source_pages": 0, "source": None}
    return {"index_loaded": n > 0, "chunks": n, "source_pages": int(source.get("pages", 0)) if n else 0,
            "source": source.get("title") if n else None}
