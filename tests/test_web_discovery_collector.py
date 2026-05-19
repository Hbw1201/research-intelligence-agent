from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.collectors.page_fetcher import FetchedPage, PageFetchResult
from backend.collectors.web_collector import WebDiscoveryCollector
from backend.config import Settings
from backend.search.search_result import SearchResult


class FakeSearchClient:
    def __init__(self, results: list[SearchResult] | dict[str, list[SearchResult]]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    async def search(self, query: str, max_results: int) -> list[SearchResult]:
        self.calls.append({"query": query, "max_results": max_results})
        if isinstance(self.results, dict):
            return self.results.get(query, [])[:max_results]
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
    query_expansion: bool = False,
    query_categories: str = "general,news,blog,dataset,benchmark,lab,company_research",
    results_per_query: int = 5,
    total_max_results: int = 30,
) -> Settings:
    return Settings(
        _env_file=None,
        web_discovery_allowed_domains=allowed_domains,
        web_discovery_blocked_domains=blocked_domains,
        web_discovery_max_results=max_results,
        web_discovery_fetch_pages=fetch_pages,
        web_discovery_query_expansion=query_expansion,
        web_discovery_query_categories=query_categories,
        web_discovery_results_per_query=results_per_query,
        web_discovery_total_max_results=total_max_results,
    )


def search_result(url: str = "https://example.com/update", title: str = "Search title") -> SearchResult:
    return SearchResult(
        title=title,
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
    assert item.metadata["search_query"] == "single-cell"
    assert item.metadata["search_category"] == "general"
    assert item.metadata["searxng_engine"] == "searxng"
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


@pytest.mark.anyio
async def test_web_discovery_collector_calls_search_multiple_times_when_expansion_enabled() -> None:
    fake_search = FakeSearchClient(
        {
            "single-cell foundation model": [search_result("https://example.com/general", title="General update")],
            "single-cell foundation model dataset": [search_result("https://zenodo.org/records/1", title="Dataset update")],
            "single-cell foundation model benchmark": [
                search_result("https://example.com/benchmark", title="Benchmark update")
            ],
        }
    )
    collector = WebDiscoveryCollector(
        search_client=fake_search,
        settings=make_settings(
            query_expansion=True,
            query_categories="general,dataset,benchmark",
            results_per_query=2,
            total_max_results=10,
        ),
        page_fetcher=FakePageFetcher(),  # type: ignore[arg-type]
    )

    items = await collector.collect(query="single-cell foundation model", max_results=10)

    assert [call["query"] for call in fake_search.calls] == [
        "single-cell foundation model",
        "single-cell foundation model dataset",
        "single-cell foundation model benchmark",
    ]
    assert [item.url for item in items] == [
        "https://example.com/general",
        "https://zenodo.org/records/1",
        "https://example.com/benchmark",
    ]
    assert items[1].item_type == "dataset"
    assert items[2].item_type == "benchmark"
    assert items[1].metadata["search_category"] == "dataset"


@pytest.mark.anyio
async def test_web_discovery_collector_deduplicates_results_from_multiple_queries() -> None:
    duplicate_a = SearchResult(
        title="Same update",
        url="https://example.com/update?utm_source=newsletter",
        snippet="General result.",
        source="searxng",
    )
    duplicate_b = SearchResult(
        title="Same update",
        url="http://example.com/update/?utm_campaign=lab",
        snippet="Dataset result.",
        source="searxng",
    )
    unique = SearchResult(
        title="Different update",
        url="https://example.com/different",
        snippet="Different result.",
        source="searxng",
    )
    fake_search = FakeSearchClient(
        {
            "single-cell": [duplicate_a],
            "single-cell dataset": [duplicate_b, unique],
        }
    )
    collector = WebDiscoveryCollector(
        search_client=fake_search,
        settings=make_settings(query_expansion=True, query_categories="general,dataset", results_per_query=5),
        page_fetcher=FakePageFetcher(),  # type: ignore[arg-type]
    )

    items = await collector.collect(query="single-cell", max_results=10)

    assert [item.title for item in items] == ["Same update", "Different update"]
    assert [item.url for item in items] == ["https://example.com/update", "https://example.com/different"]


@pytest.mark.anyio
async def test_web_discovery_collector_respects_total_max_results() -> None:
    fake_search = FakeSearchClient(
        {
            "single-cell": [
                search_result("https://example.com/a", title="A"),
                search_result("https://example.com/b", title="B"),
            ],
            "single-cell news": [
                search_result("https://example.com/c", title="C"),
                search_result("https://example.com/d", title="D"),
            ],
            "single-cell dataset": [
                search_result("https://example.com/e", title="E"),
                search_result("https://example.com/f", title="F"),
            ],
        }
    )
    collector = WebDiscoveryCollector(
        search_client=fake_search,
        settings=make_settings(
            max_results=20,
            query_expansion=True,
            query_categories="general,news,dataset",
            results_per_query=2,
            total_max_results=3,
        ),
        page_fetcher=FakePageFetcher(),  # type: ignore[arg-type]
    )

    items = await collector.collect(query="single-cell", max_results=10)

    assert len(items) == 3
    assert [item.url for item in items] == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    assert [call["max_results"] for call in fake_search.calls] == [2, 2]
