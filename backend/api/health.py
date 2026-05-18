from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["multi-agent-intel"]


@router.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok", service="multi-agent-intel")
