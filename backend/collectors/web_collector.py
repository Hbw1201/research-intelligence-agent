from __future__ import annotations

from datetime import date
import logging
from urllib.parse import urlparse, urlunparse

import httpx

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.content_extractor import ContentExtractor
from backend.collectors.errors import ConciseCollectorError, concise_error_message
from backend.collectors.page_fetcher import PageFetchResult, PageFetcher
from backend.collectors.rss_discovery import discover_feed_urls
from backend.config import Settings, get_settings
from backend.services.item_fingerprint import normalize_canonical_url, normalize_title
from backend.search.web_query_planner import PlannedWebQuery, WebQueryPlanner
from backend.search.web_result_classifier import WebResultClassifier
from backend.search.search_result import SearchResult
from backend.search.searxng_errors import SearxNGBlockedEnginesError
from backend.search.web_search_client import WebSearchClient


logger = logging.getLogger(__name__)


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
        query_planner: WebQueryPlanner | None = None,
        result_classifier: WebResultClassifier | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self.search_client = search_client
        self.settings = settings or get_settings()
        self.page_fetcher = page_fetcher
        self.content_extractor = content_extractor or ContentExtractor()
        self.query_planner = query_planner or WebQueryPlanner(categories=self._query_categories())
        self.result_classifier = result_classifier or WebResultClassifier()

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Search the web and normalize results into ResearchItem records."""
        del start_date, end_date
        limit = self._total_limit(max_results)
        if not query.strip() or limit <= 0:
            return []

        planned_queries = self._planned_queries(query)
        search_results = await self._search_planned_queries(planned_queries, limit)
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
        item_type = self.result_classifier.classify(result)
        return ResearchItem(
            title=extracted_title or result.title,
            abstract=abstract,
            url=canonical_url,
            source_name="web",
            source_type=self.result_classifier.source_type_for_item_type(item_type),
            item_type=item_type,
            authors=[],
            published_at=result.published_at,
            raw_text=raw_text,
            external_id=canonical_url,
            keywords=[],
            metadata={
                "page_fetch_status": page_fetch_status,
                "search_query": result.metadata.get("search_query"),
                "search_category": result.metadata.get("search_category"),
                "search_source": result.source,
                "searxng_engine": result.metadata.get("searxng_engine") or result.source,
                "snippet": result.snippet,
                "discovered_feeds": discovered_feeds,
                "search_metadata": result.metadata,
            },
        )

    async def _search_planned_queries(self, planned_queries: list[PlannedWebQuery], limit: int) -> list[SearchResult]:
        merged: list[SearchResult] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        failed_query_errors: list[str] = []
        per_query_limit = self._per_query_limit(limit)
        for planned in planned_queries:
            if len(merged) >= limit:
                break
            try:
                results = await self.search_client.search(query=planned.query, max_results=per_query_limit)
            except Exception as exc:  # noqa: BLE001 - isolate one expanded search query.
                message = self._expanded_query_error_message(exc)
                failed_query_errors.append(message)
                logger.warning(
                    "%s",
                    message,
                    extra={"query": planned.query, "search_category": planned.category},
                )
                logger.debug("Expanded web discovery query failed", exc_info=True)
                continue
            for result in results:
                url_key = normalize_canonical_url(result.url)
                title_key = normalize_title(result.title)
                if url_key and url_key in seen_urls:
                    continue
                if title_key and title_key in seen_titles:
                    continue
                seen_urls.add(url_key)
                seen_titles.add(title_key)
                merged.append(self._with_search_metadata(result, planned))
                if len(merged) >= limit:
                    break
        if not merged and failed_query_errors:
            raise ConciseCollectorError(failed_query_errors[0], retryable=False)
        return merged

    def _planned_queries(self, query: str) -> list[PlannedWebQuery]:
        if not self.settings.web_discovery_query_expansion:
            return [PlannedWebQuery(query=" ".join(query.split()), category="general")]
        return self.query_planner.plan_with_categories(query)

    def _total_limit(self, max_results: int) -> int:
        configured_limit = max(0, self.settings.web_discovery_max_results)
        total_limit = max(0, self.settings.web_discovery_total_max_results)
        positive_limits = [value for value in (max_results, configured_limit, total_limit) if value > 0]
        return min(positive_limits) if positive_limits else 0

    def _per_query_limit(self, total_limit: int) -> int:
        configured = max(1, self.settings.web_discovery_results_per_query)
        return max(1, min(configured, total_limit))

    def _query_categories(self) -> list[str]:
        return [
            part.strip()
            for part in self.settings.web_discovery_query_categories.split(",")
            if part.strip()
        ]

    @staticmethod
    def _with_search_metadata(result: SearchResult, planned: PlannedWebQuery) -> SearchResult:
        metadata = dict(result.metadata)
        metadata["search_query"] = planned.query
        metadata["search_category"] = planned.category
        metadata["searxng_engine"] = result.source
        return result.model_copy(update={"metadata": metadata})

    @staticmethod
    def _expanded_query_error_message(exc: Exception) -> str:
        if isinstance(exc, SearxNGBlockedEnginesError):
            return str(exc)
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 400:
            return "SearxNG query failed with HTTP 400 for one expanded query"
        return f"SearxNG query failed for one expanded query: {concise_error_message(exc)}"

    async def _fetch_page_if_enabled(self, url: str) -> PageFetchResult | None:
        if not self.settings.web_discovery_fetch_pages:
            return PageFetchResult(status="disabled", reason="disabled")
        return await self._page_fetcher().fetch(url)

    def _page_fetcher(self) -> PageFetcher:
        if self.page_fetcher is None:
            self.page_fetcher = PageFetcher(settings=self.settings, config=self.config)
        return self.page_fetcher

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
        normalized = normalize_canonical_url(url)
        if normalized:
            return normalized
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
