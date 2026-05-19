from __future__ import annotations

from datetime import date
from urllib.parse import urlparse, urlunparse

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.content_extractor import ContentExtractor
from backend.collectors.page_fetcher import PageFetchResult, PageFetcher
from backend.collectors.rss_discovery import discover_feed_urls
from backend.config import Settings, get_settings
from backend.search.search_result import SearchResult
from backend.search.web_search_client import WebSearchClient


class WebDiscoveryCollector(BaseCollector):
    """General web discovery collector backed by a web search provider."""

    name = "web"

    def __init__(
        self,
        search_client: WebSearchClient,
        settings: Settings | None = None,
        config: CollectorConfig | None = None,
        page_fetcher: PageFetcher | None = None,
        content_extractor: ContentExtractor | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self.search_client = search_client
        self.settings = settings or get_settings()
        self.page_fetcher = page_fetcher or PageFetcher(settings=self.settings, config=self.config)
        self.content_extractor = content_extractor or ContentExtractor()

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Search the web and normalize results into ResearchItem records."""
        del start_date, end_date
        limit = max(0, min(max_results, self.settings.web_discovery_max_results))
        if not query.strip() or limit <= 0:
            return []

        search_results = await self.search_client.search(query=query, max_results=limit)
        items: list[ResearchItem] = []
        for result in search_results:
            if len(items) >= limit:
                break
            if not self._domain_allowed(result.url):
                continue
            items.append(await self._to_research_item(result))
        return items

    async def _to_research_item(self, result: SearchResult) -> ResearchItem:
        canonical_url = self._canonicalize_url(result.url)
        fetch_result = await self._fetch_page_if_enabled(canonical_url)
        page = fetch_result.page if fetch_result else None
        page_fetch_status = fetch_result.status if fetch_result else "not_fetched"

        extracted_title: str | None = None
        extracted_text = ""
        discovered_feeds: list[str] = []
        if page is not None:
            extracted = self.content_extractor.extract(page.content, page.content_type)
            extracted_title = extracted.title
            extracted_text = extracted.text
            if page.content_type and "html" in page.content_type:
                discovered_feeds = discover_feed_urls(canonical_url, page.content)

        abstract = result.snippet or self._truncate(extracted_text, 500) or None
        raw_text = extracted_text or result.snippet or None
        return ResearchItem(
            title=extracted_title or result.title,
            abstract=abstract,
            url=canonical_url,
            source_name="web",
            source_type="web",
            item_type="webpage",
            authors=[],
            published_at=result.published_at,
            raw_text=raw_text,
            external_id=canonical_url,
            keywords=[],
            metadata={
                "page_fetch_status": page_fetch_status,
                "search_source": result.source,
                "snippet": result.snippet,
                "discovered_feeds": discovered_feeds,
                "search_metadata": result.metadata,
            },
        )

    async def _fetch_page_if_enabled(self, url: str) -> PageFetchResult | None:
        if not self.settings.web_discovery_fetch_pages:
            return None
        return await self.page_fetcher.fetch(url)

    def _domain_allowed(self, url: str) -> bool:
        domain = self._domain(url)
        if not domain:
            return False

        allowed_domains = self._settings_domains(self.settings.web_discovery_allowed_domains)
        blocked_domains = self._settings_domains(self.settings.web_discovery_blocked_domains)
        if blocked_domains and self._matches_domain(domain, blocked_domains):
            return False
        if allowed_domains and not self._matches_domain(domain, allowed_domains):
            return False
        return True

    @staticmethod
    def _settings_domains(value: str | None) -> set[str]:
        return {
            part.strip().lower().lstrip(".")
            for part in (value or "").split(",")
            if part.strip()
        }

    @staticmethod
    def _matches_domain(domain: str, domains: set[str]) -> bool:
        return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in domains)

    @staticmethod
    def _domain(url: str) -> str:
        return (urlparse(url).hostname or "").lower()

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        return urlunparse((scheme, netloc, path, "", parsed.query, ""))

    @staticmethod
    def _truncate(text: str, max_chars: int) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 3].rstrip() + "..."
