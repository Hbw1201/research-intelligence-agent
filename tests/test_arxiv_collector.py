from datetime import date, datetime, timezone
from typing import Any

import pytest

from backend.collectors.arxiv_collector import ARXIV_API_URL, ArxivCollector
from backend.collectors.base import CollectorConfig, ResearchItem


ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2605.12345v1</id>
    <updated>2026-05-19T00:00:00Z</updated>
    <published>2026-05-18T12:30:00Z</published>
    <title>  Test
      Paper  </title>
    <summary>  A useful
      abstract.  </summary>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" />
    <category term="cs.LG" />
    <arxiv:doi>10.1234/example</arxiv:doi>
    <arxiv:comment>5 pages</arxiv:comment>
    <link href="https://arxiv.org/abs/2605.12345v1" rel="alternate" type="text/html" />
    <link title="pdf" href="https://arxiv.org/pdf/2605.12345v1" rel="related" type="application/pdf" />
  </entry>
</feed>
"""


EMPTY_ATOM_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"></feed>
"""


class FakeResponse:
    def __init__(self, text: str = ATOM_RESPONSE) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeRequestsGet:
    def __init__(self, responses: list[FakeResponse] | None = None, failures: int = 0) -> None:
        self.responses = responses or [FakeResponse()]
        self.failures = failures
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if len(self.calls) <= self.failures:
            raise TimeoutError("temporary failure")
        index = min(len(self.calls) - self.failures - 1, len(self.responses) - 1)
        return self.responses[index]


@pytest.mark.anyio
async def test_arxiv_collector_empty_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector()

    items = await collector.collect(query="graph neural networks", max_results=10)

    assert items == []
    assert fake_get.calls[0]["url"] == ARXIV_API_URL


@pytest.mark.anyio
async def test_arxiv_collector_normalizes_atom_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector()

    items = await collector.collect(query="ai agents", max_results=1)

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, ResearchItem)
    assert item.title == "Test Paper"
    assert item.abstract == "A useful abstract."
    assert item.url == "https://arxiv.org/abs/2605.12345v1"
    assert item.source_name == "arxiv"
    assert item.source_type == "paper"
    assert item.item_type == "paper"
    assert item.authors == ["Ada Lovelace", "Alan Turing"]
    assert item.published_at == datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc)
    assert item.raw_text == "Test Paper\n\nA useful abstract."
    assert item.external_id == "2605.12345v1"
    assert item.keywords == ["cs.AI", "cs.LG"]
    assert item.metadata["arxiv_id"] == "2605.12345v1"
    assert item.metadata["primary_category"] == "cs.AI"
    assert item.metadata["pdf_url"] == "https://arxiv.org/pdf/2605.12345v1"
    assert item.metadata["doi"] == "10.1234/example"
    assert item.metadata["comment"] == "5 pages"


@pytest.mark.anyio
async def test_arxiv_collector_request_params_include_sort_and_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector()

    items = await collector.collect(query="retrieval augmented generation", max_results=2)

    assert len(items) == 1
    params = fake_get.calls[0]["params"]
    assert params == {
        "search_query": "all:retrieval augmented generation",
        "start": 0,
        "max_results": 2,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }


@pytest.mark.anyio
async def test_arxiv_collector_adds_date_range_to_query(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector()

    await collector.collect(
        query="multi agent systems",
        max_results=5,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 18),
    )

    assert fake_get.calls[0]["params"]["search_query"] == (
        "(all:multi agent systems) AND submittedDate:[202605010000 TO 202605182359]"
    )


@pytest.mark.anyio
async def test_arxiv_collector_retries_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(ATOM_RESPONSE)], failures=1)
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector(config=CollectorConfig(max_retries=2))

    items = await collector.collect(query="ai", max_results=1)

    assert len(items) == 1
    assert len(fake_get.calls) == 2


@pytest.mark.anyio
async def test_arxiv_collector_passes_proxy_dict_to_requests_get(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector(config=CollectorConfig(proxy="http://127.0.0.1:7897"))

    await collector.collect(query="single cell", max_results=1)

    assert fake_get.calls[0]["proxies"] == {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }


@pytest.mark.anyio
async def test_arxiv_collector_passes_separate_proxy_dict_to_requests_get(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector(
        config=CollectorConfig(
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    await collector.collect(query="single cell", max_results=1)

    assert fake_get.calls[0]["proxies"] == {
        "http": "http://127.0.0.1:7898",
        "https": "http://127.0.0.1:7899",
    }


@pytest.mark.anyio
async def test_arxiv_collector_passes_timeout_to_requests_get(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector(
        config=CollectorConfig(
            collector_timeout_seconds=60,
            arxiv_timeout_seconds=30,
        )
    )

    await collector.collect(query="single cell", max_results=1)

    assert fake_get.calls[0]["timeout"] == 30.0


@pytest.mark.anyio
async def test_arxiv_collector_uses_collector_timeout_when_arxiv_timeout_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector(config=CollectorConfig(collector_timeout_seconds=60))

    await collector.collect(query="single cell", max_results=1)

    assert fake_get.calls[0]["timeout"] == 60.0


@pytest.mark.anyio
async def test_arxiv_collector_defaults_timeout_to_120_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_get = FakeRequestsGet([FakeResponse(EMPTY_ATOM_RESPONSE)])
    monkeypatch.setattr("backend.collectors.arxiv_collector.requests.get", fake_get)
    collector = ArxivCollector()

    await collector.collect(query="single cell", max_results=1)

    assert fake_get.calls[0]["timeout"] == 120.0
