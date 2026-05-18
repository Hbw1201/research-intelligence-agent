from datetime import date, datetime, timezone
from time import struct_time
from typing import Any

import pytest

from backend.collectors.base import CollectorConfig
from backend.collectors.rss_collector import RSSCollector


class FakeResponse:
    text = "<rss></rss>"

    def raise_for_status(self) -> None:
        return None


class FakeRSSClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        return FakeResponse()


class FakeAsyncClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def get(self, url: str) -> FakeResponse:
        return FakeResponse()


def parser_with_entries(entries: list[dict[str, Any]]) -> Any:
    def parse(text: str) -> dict[str, Any]:
        assert text == "<rss></rss>"
        return {
            "feed": {"title": "AI Updates"},
            "entries": entries,
        }

    return parse


def fake_entry(title: str = "Agent Research News", published_day: int = 18) -> dict[str, Any]:
    return {
        "title": title,
        "summary": "  Fresh technical update.  ",
        "link": "https://example.org/news",
        "id": "entry-1",
        "authors": [{"name": "Ada Lovelace"}],
        "published_parsed": struct_time((2026, 5, published_day, 10, 0, 0, 0, 0, 0)),
    }


@pytest.mark.anyio
async def test_rss_collector_empty_results() -> None:
    collector = RSSCollector(
        feed_url="https://example.org/feed.xml",
        client=FakeRSSClient(),
        parser=parser_with_entries([]),
    )

    items = await collector.collect(query="agents", max_results=5)

    assert items == []


@pytest.mark.anyio
async def test_rss_collector_normalizes_entry() -> None:
    collector = RSSCollector(
        feed_url="https://example.org/feed.xml",
        client=FakeRSSClient(),
        parser=parser_with_entries([fake_entry()]),
    )

    items = await collector.collect(query="agent", max_results=1)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Agent Research News"
    assert item.abstract == "Fresh technical update."
    assert item.url == "https://example.org/news"
    assert item.source_name == "AI Updates"
    assert item.source_type == "news"
    assert item.item_type == "feed_entry"
    assert item.authors == ["Ada Lovelace"]
    assert item.published_at == datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    assert item.external_id == "entry-1"
    assert item.metadata["feed_url"] == "https://example.org/feed.xml"


@pytest.mark.anyio
async def test_rss_collector_max_results_and_date_filter() -> None:
    collector = RSSCollector(
        feed_url="https://example.org/feed.xml",
        client=FakeRSSClient(),
        parser=parser_with_entries(
            [
                fake_entry(title="Agent update one", published_day=1),
                fake_entry(title="Agent update two", published_day=18),
                fake_entry(title="Agent update three", published_day=19),
            ]
        ),
    )

    items = await collector.collect(
        query="agent",
        max_results=1,
        start_date=date(2026, 5, 2),
        end_date=date(2026, 5, 18),
    )

    assert len(items) == 1
    assert items[0].title == "Agent update two"


@pytest.mark.anyio
async def test_rss_collector_uses_explicit_proxy_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.rss_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = RSSCollector(
        feed_url="https://example.org/feed.xml",
        config=CollectorConfig(proxy="http://127.0.0.1:7897"),
        parser=parser_with_entries([]),
    )

    items = await collector.collect(query="agents", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [
        {
            "timeout": 20.0,
            "proxy": "http://127.0.0.1:7897",
            "trust_env": False,
        }
    ]


@pytest.mark.anyio
async def test_rss_collector_preserves_default_client_behavior_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.rss_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = RSSCollector(
        feed_url="https://example.org/feed.xml",
        config=CollectorConfig(),
        parser=parser_with_entries([]),
    )

    items = await collector.collect(query="agents", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [{"timeout": 20.0}]
