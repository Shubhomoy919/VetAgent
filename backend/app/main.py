from fastapi import FastAPI

from app.api import health

app = FastAPI(
    title="VetAgentBench-IN",
    description="Research prototype — not for clinical use.",
    version="0.1.0",
)

app.include_router(health.router)
