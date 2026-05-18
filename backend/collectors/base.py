from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CollectorConfig:
    """Shared collector runtime constraints."""

    max_retries: int
    rate_limit_per_minute: int


@dataclass(frozen=True)
class CollectedItem:
    """Normalized placeholder shape for collected research updates."""

    source: str
    title: str
    url: str | None = None
    summary: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCollector(ABC):
    """Base interface for future collectors."""

    name: str

    def __init__(self, config: CollectorConfig) -> None:
        self.config = config

    @abstractmethod
    async def collect(self) -> list[CollectedItem]:
        """Collect and normalize source items."""
