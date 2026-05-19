from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.collectors.page_fetcher import FetchedPage, PageFetchResult
from backend.collectors.web_collector import WebDiscoveryCollector
from backend.config import Settings
from backend.search.search_result import SearchResult


class FakeSearchClient:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append({"query": query, "max_results": max_results})
        return self.results[:max_results]


class FakePageFetcher:
    def __init__(self, results: dict[str, PageFetchResult] | None = None) -> None:
        self.results = results or {}
        self.calls: list[str] = []

    async def fetch(self, url: str) -> PageFetchResult:
        self.calls.append(url)
        return self.results.get(url, PageFetchResult(status="not_found"))


def make_settings(
    allowed_domains: str | None = None,
    blocked_domains: str | None = None,
    max_results: int = 20,
    fetch_pages: bool = False,
) -> Settings:
    return Settings(
        _env_file=None,
        web_discovery_allowed_domains=allowed_domains,
        web_discovery_blocked_domains=blocked_domains,
        web_discovery_max_results=max_results,
        web_discovery_fetch_pages=fetch_pages,
    )


def search_result(url: str = "https://example.com/update") -> SearchResult:
    return SearchResult(
        title="Search title",
        url=url,
        snippet="Search snippet",
        source="searxng",
        published_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )


@pytest.mark.anyio
async def test_web_discovery_collector_converts_search_results_to_research_items() -> None:
    page = FetchedPage(
        url="https://example.com/update",
        content="""
        <html>
          <head>
            <title>Page title</title>
            <link rel="alternate" type="application/rss+xml" href="/rss.xml">
          </head>
          <body><nav>menu</nav><main>Readable discovery text.</main></body>
        </html>
        """,
        content_type="text/html",
    )
    fetcher = FakePageFetcher({"https://example.com/update": PageFetchResult(status="fetched", page=page)})
    collector = WebDiscoveryCollector(
        search_client=FakeSearchClient([search_result()]),
        settings=make_settings(fetch_pages=True),
        page_fetcher=fetcher,  # type: ignore[arg-type]
    )

    items = await collector.collect(query="single-cell", max_results=5)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Page title"
    assert item.abstract == "Search snippet"
    assert item.url == "https://example.com/update"
    assert item.source_name == "web"
    assert item.source_type == "web"
    assert item.item_type == "webpage"
    assert item.external_id == "https://example.com/update"
    assert "Readable discovery text." in (item.raw_text or "")
    assert item.metadata["page_fetch_status"] == "fetched"
    assert item.metadata["search_source"] == "searxng"
    assert "https://example.com/rss.xml" in item.metadata["discovered_feeds"]


@pytest.mark.anyio
async def test_web_discovery_collector_domain_allowlist_filters_results() -> None:
    results = [
        search_result("https://allowed.example/a"),
        search_result("https://blocked.example/b"),
    ]
    fetcher = FakePageFetcher()
    collector = WebDiscoveryCollector(
        search_client=FakeSearchClient(results),
        settings=make_settings(allowed_domains="allowed.example"),
        page_fetcher=fetcher,  # type: ignore[arg-type]
    )

    items = await collector.collect(query="agent", max_results=10)

    assert [item.url for item in items] == ["https://allowed.example/a"]
    assert fetcher.calls == []


@pytest.mark.anyio
async def test_web_discovery_collector_domain_blocklist_filters_results() -> None:
    results = [
        search_result("https://allowed.example/a"),
        search_result("https://blocked.example/b"),
    ]
    fetcher = FakePageFetcher()
    collector = WebDiscoveryCollector(
        search_client=FakeSearchClient(results),
        settings=make_settings(blocked_domains="blocked.example"),
        page_fetcher=fetcher,  # type: ignore[arg-type]
    )

    items = await collector.collect(query="agent", max_results=10)

    assert [item.url for item in items] == ["https://allowed.example/a"]
    assert fetcher.calls == []


@pytest.mark.anyio
async def test_web_discovery_collector_fetch_pages_false_avoids_page_fetcher() -> None:
    fetcher = FakePageFetcher()
    collector = WebDiscoveryCollector(
        search_client=FakeSearchClient([search_result()]),
        settings=make_settings(fetch_pages=False),
        page_fetcher=fetcher,  # type: ignore[arg-type]
    )

    items = await collector.collect(query="agent", max_results=10)

    assert len(items) == 1
    assert fetcher.calls == []
    assert items[0].abstract == "Search snippet"
    assert items[0].raw_text == "Search snippet"
    assert items[0].metadata["page_fetch_status"] == "not_fetched"


@pytest.mark.anyio
async def test_web_discovery_collector_returns_item_when_page_fetch_is_403() -> None:
    fetcher = FakePageFetcher(
        {
            "https://example.com/update": PageFetchResult(
                status="skipped_403",
                reason="blocked_403",
                status_code=403,
            )
        }
    )
    collector = WebDiscoveryCollector(
        search_client=FakeSearchClient([search_result()]),
        settings=make_settings(fetch_pages=True),
        page_fetcher=fetcher,  # type: ignore[arg-type]
    )

    items = await collector.collect(query="agent", max_results=10)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Search title"
    assert item.abstract == "Search snippet"
    assert item.raw_text == "Search snippet"
    assert item.metadata["page_fetch_status"] == "skipped_403"
    assert item.metadata["search_source"] == "searxng"
    assert item.metadata["snippet"] == "Search snippet"
