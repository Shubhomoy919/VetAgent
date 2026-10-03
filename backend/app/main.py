import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import data, health, runs, scorecard
from app.config import get_settings
from app.data.editor import EditError
from app.retrieval.service import svtg_index


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Warm the SVTG index in the background so the first search is fast.
    threading.Thread(target=lambda: svtg_index(get_settings()), daemon=True).start()
    yield


app = FastAPI(
    title="VetAgentBench-IN",
    description="Research prototype — not for clinical use.",
    version="0.6.0",
    lifespan=lifespan,
)


@app.exception_handler(EditError)
async def edit_error_handler(_: Request, exc: EditError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "errors": exc.errors})


app.include_router(health.router)
app.include_router(data.router)
app.include_router(runs.router)
app.include_router(scorecard.router)
