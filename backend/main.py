from fastapi import FastAPI

from backend.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Multi-Agent Research Intelligence",
        description="MVP backend for personalized research intelligence collection.",
        version="0.1.0",
    )
    app.include_router(health_router)
    return app


app = create_app()
