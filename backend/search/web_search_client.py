from __future__ import annotations

from typing import Protocol

from backend.search.search_result import SearchResult


class WebSearchClient(Protocol):
    """Protocol for pluggable web search providers."""

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Search the web and return normalized results."""
