import logging
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import auth, data, health, review, runs, scorecard, settings
from app.config import REPO_ROOT, get_settings
from app.data.editor import EditError
from app.retrieval.service import svtg_index
from app.security import BodySizeLimit, GuardMiddleware, install_log_redaction, redact

log = logging.getLogger("vetagentbench")

# Built frontend (npm run build). Present in the Docker image and after a local production build.
DIST = Path(__import__("os").environ.get("FRONTEND_DIST") or REPO_ROOT / "frontend" / "dist").resolve()


def _startup() -> None:
    s = get_settings()
    from app.agent.manager import manager
    from app.snapshot import SnapshotError, load_snapshot

    store = manager.store
    interrupted = store.mark_interrupted()
    if interrupted:
        log.info("Marked %d run(s) interrupted by a restart", interrupted)
    if s.is_production:
        removed = store.delete_demo_runs()
        if removed:
            log.info("Removed %d demo run(s) from the production database", removed)
    if s.autoload_snapshot and s.snapshot_file.is_file():
        try:
            rid = load_snapshot(store, s.snapshot_file)
            if rid:
                log.info("Loaded frozen results snapshot %s", rid)
        except (SnapshotError, OSError, ValueError) as e:
            log.error("Could not load results snapshot: %s", e)


@asynccontextmanager
async def lifespan(_: FastAPI):
    install_log_redaction()
    _startup()
    # Warm the SVTG index in the background so the first search is fast.
    threading.Thread(target=lambda: svtg_index(get_settings()), daemon=True).start()
    yield
    from app.agent.manager import manager

    log.info("Shutting down: stopping any active run")
    manager.shutdown(timeout=20.0)


_s = get_settings()
app = FastAPI(
    title="VetAgentBench-IN",
    description="Research prototype, not for clinical use.",
    version=__version__,
    lifespan=lifespan,
    debug=False,
    docs_url=None if _s.is_production else "/api/docs",
    redoc_url=None,
    openapi_url=None if _s.is_production else "/api/openapi.json",
)


@app.exception_handler(EditError)
async def edit_error_handler(_: Request, exc: EditError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "errors": exc.errors})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Field locations and messages only; never echo the submitted values back.
    errors = [{"loc": list(e.get("loc", [])), "msg": str(e.get("msg", ""))} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "Request failed validation", "errors": errors[:50]})


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # The traceback goes to the server log (redacted); the client gets a reference, never a stack trace.
    ref = uuid.uuid4().hex[:10]
    log.error("Unhandled error %s on %s %s: %s", ref, request.method, request.url.path,
              redact(f"{type(exc).__name__}: {exc}"), exc_info=not get_settings().is_production)
    return JSONResponse(status_code=500, content={"detail": f"Internal server error (reference {ref})."})


# Order: the last added runs first. BodySizeLimit wraps everything; Guard adds headers and limits.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
if _s.origins:
    app.add_middleware(CORSMiddleware, allow_origins=_s.origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])
app.add_middleware(GuardMiddleware)
app.add_middleware(BodySizeLimit)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(data.router)
app.include_router(runs.router)
app.include_router(scorecard.router)
app.include_router(review.router)
app.include_router(settings.router)


# ---------- the built frontend ----------

PRECOMPRESSED = (("br", ".br"), ("gzip", ".gz"))
MEDIA = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".html": "text/html; charset=utf-8",
         ".json": "application/json", ".woff2": "font/woff2", ".woff": "font/woff", ".png": "image/png",
         ".txt": "text/plain; charset=utf-8", ".webmanifest": "application/manifest+json", ".ico": "image/x-icon"}


def _static(path: Path, request: Request, immutable: bool) -> Response:
    """Serve a file, preferring a build-time .br or .gz sibling when the browser accepts it."""
    accept = request.headers.get("accept-encoding", "")
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable" if immutable else "no-cache",
        "Vary": "Accept-Encoding",
    }
    media = MEDIA.get(path.suffix, "application/octet-stream")
    for enc, ext in PRECOMPRESSED:
        alt = path.with_name(path.name + ext)
        if enc in accept and alt.is_file():
            return FileResponse(alt, media_type=media, headers={**headers, "Content-Encoding": enc})
    return FileResponse(path, media_type=media, headers=headers)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(rest: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.get("/{rest:path}", include_in_schema=False)
def frontend(rest: str, request: Request) -> Response:
    index = DIST / "index.html"
    if not index.is_file():
        raise StarletteHTTPException(status_code=404, detail="Frontend not built. Run: npm --prefix frontend run build")
    candidate = (DIST / rest).resolve()
    if rest and candidate.is_file() and candidate.is_relative_to(DIST) and not candidate.name.endswith((".br", ".gz")):
        return _static(candidate, request, immutable=rest.startswith("assets/"))
    # Client-side routes (and unknown paths) get the app shell; the app renders its own 404 page.
    return _static(index, request, immutable=False)
