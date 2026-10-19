"""Vercel entry point: the FastAPI app as one Python function.

vercel.json sends every /api/* request here; the built frontend is served from the CDN. The app itself lives in
backend/app (see backend/app/main.py).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
