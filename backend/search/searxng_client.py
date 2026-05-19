from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import httpx

from backend.collectors.base import CollectorConfig
from backend.collectors.proxy import collector_proxy_config
from backend.config import Settings, get_settings
from backend.search.search_result import SearchResult


logger = logging.getLogger(__name__)


class SearxNGClient:
    """SearxNG JSON API client."""

    def __init__(
        self,
        settings: Settings | None = None,
        config: CollectorConfig | None = None,
        http_client: httpx.AsyncClient | Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.config = config or CollectorConfig()
        self._http_client = http_client

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        """Search SearxNG and normalize JSON results."""
        normalized_query = " ".join(query.split())
        if not normalized_query or max_results <= 0:
            return []

        params = {
            "q": normalized_query,
            "format": "json",
            "language": "auto",
            "categories": "general",
        }
        response = await self._get(params)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return []

        raw_results = data.get("results", [])
        if not isinstance(raw_results, list):
            return []

        results: list[SearchResult] = []
        for raw_result in raw_results[:max_results]:
            if not isinstance(raw_result, dict):
                continue
            result = self._parse_result(raw_result)
            if result is not None:
                results.append(result)
        return results

    async def _get(self, params: dict[str, str]) -> httpx.Response:
        base_url = self.settings.web_search_base_url.rstrip("/")
        url = f"{base_url}/search"
        timeout = self.config.collector_timeout_seconds or self.config.timeout_seconds

        logger.info(
            "Calling SearxNG search provider=%s max_results_query=%s",
            self.settings.web_search_provider,
            params.get("q"),
            extra={
                "provider": self.settings.web_search_provider,
                "query": params.get("q"),
            },
        )
        if self._http_client is not None:
            return await self._http_client.get(url, params=params, timeout=timeout)

        client_kwargs: dict[str, Any] = {"timeout": timeout}
        client_kwargs.update(collector_proxy_config(self.config).httpx_client_kwargs())
        async with httpx.AsyncClient(**client_kwargs) as client:
            return await client.get(url, params=params)

    @classmethod
    def _parse_result(cls, raw_result: dict[str, Any]) -> SearchResult | None:
        title = cls._clean_text(raw_result.get("title"))
        url = cls._clean_text(raw_result.get("url"))
        if not title or not url:
            return None

        snippet = cls._clean_text(raw_result.get("content") or raw_result.get("snippet"))
        source = cls._clean_text(raw_result.get("engine") or raw_result.get("source") or "searxng")
        return SearchResult(
            title=title,
            url=url,
            snippet=snippet,
            source=source or "searxng",
            published_at=cls._parse_datetime(raw_result.get("publishedDate")),
            metadata={
                "engines": raw_result.get("engines"),
                "category": raw_result.get("category"),
                "score": raw_result.get("score"),
            },
        )

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _clean_text(value: Any) -> str:
        if value is None:
            return ""
        return " ".join(str(value).split())
