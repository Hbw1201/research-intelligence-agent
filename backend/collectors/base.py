from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class CollectorConfig:
    """Shared collector runtime constraints."""

    max_retries: int = 3
    timeout_seconds: float = 20.0
    rate_limit_delay_seconds: float = 0.0


class ResearchItem(BaseModel):
    """Normalized schema for collected research updates."""

    title: str
    abstract: str | None = None
    url: str
    source_name: str
    source_type: str
    item_type: str
    authors: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    raw_text: str | None = None
    external_id: str | None = None
    keywords: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


CollectedItem = ResearchItem


class BaseCollector(ABC):
    """Base interface for future collectors."""

    name: str

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config

    @abstractmethod
    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Collect and normalize source items."""
