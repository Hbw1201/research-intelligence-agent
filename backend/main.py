from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api.health import router as health_router
from backend.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Multi-Agent Research Intelligence",
        description="MVP backend for personalized research intelligence collection.",
        version="0.1.0",
    )
    app.include_router(health_router)
    settings = get_settings()
    report_site_dir = Path(settings.report_site_dir)
    report_site_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/reports", StaticFiles(directory=report_site_dir), name="reports")
    return app


app = create_app()
