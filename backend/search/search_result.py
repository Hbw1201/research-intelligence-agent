from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Normalized web search result."""

    title: str
    url: str
    snippet: str
    source: str
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
