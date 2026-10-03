import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import data, health, runs
from app.config import get_settings
from app.retrieval.service import svtg_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the SVTG index in the background so the first search is fast.
    threading.Thread(target=lambda: svtg_index(get_settings()), daemon=True).start()
    yield


app = FastAPI(
    title="VetAgentBench-IN",
    description="Research prototype — not for clinical use.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(data.router)
app.include_router(runs.router)
