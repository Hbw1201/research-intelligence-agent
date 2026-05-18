from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from backend.collectors.arxiv_collector import ArxivCollector
from backend.collectors.base import CollectorConfig, ResearchItem


class FakeAuthor:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeArxivResult:
    title = "  Test\nPaper  "
    summary = "  A useful\nabstract.  "
    entry_id = "https://arxiv.org/abs/2605.12345v1"
    authors = [FakeAuthor("Ada Lovelace"), FakeAuthor("Alan Turing")]
    published = datetime(2026, 5, 18, tzinfo=timezone.utc)
    updated = datetime(2026, 5, 19, tzinfo=timezone.utc)
    categories = ["cs.AI", "cs.LG"]
    primary_category = "cs.AI"
    doi = "10.1234/example"
    journal_ref = None
    comment = "5 pages"

    def get_short_id(self) -> str:
        return "2605.12345v1"


class FakeClient:
    def __init__(self, results: list[object]) -> None:
        self._results = results
        self.received_searches: list[object] = []

    def results(self, search: object) -> list[object]:
        self.received_searches.append(search)
        return self._results


def fake_search_factory(**kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


@pytest.mark.anyio
async def test_arxiv_collector_empty_results() -> None:
    collector = ArxivCollector(client=FakeClient([]), search_factory=fake_search_factory)

    items = await collector.collect(query="graph neural networks", max_results=10)

    assert items == []


@pytest.mark.anyio
async def test_arxiv_collector_normalizes_result() -> None:
    collector = ArxivCollector(client=FakeClient([FakeArxivResult()]), search_factory=fake_search_factory)

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
    assert item.published_at == datetime(2026, 5, 18, tzinfo=timezone.utc)
    assert item.raw_text == "Test Paper\n\nA useful abstract."
    assert item.external_id == "2605.12345v1"
    assert item.keywords == ["cs.AI", "cs.LG"]
    assert item.metadata["primary_category"] == "cs.AI"
    assert item.metadata["doi"] == "10.1234/example"


@pytest.mark.anyio
async def test_arxiv_collector_limits_results() -> None:
    fake_client = FakeClient([FakeArxivResult(), FakeArxivResult(), FakeArxivResult()])
    collector = ArxivCollector(client=fake_client, search_factory=fake_search_factory)

    items = await collector.collect(query="retrieval augmented generation", max_results=2)

    assert len(items) == 2
    assert fake_client.received_searches[0].max_results == 2


@pytest.mark.anyio
async def test_arxiv_collector_adds_date_range_to_query() -> None:
    fake_client = FakeClient([])
    collector = ArxivCollector(client=fake_client, search_factory=fake_search_factory)

    await collector.collect(
        query="multi agent systems",
        max_results=5,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 18),
    )

    assert fake_client.received_searches[0].query == (
        "(multi agent systems) AND submittedDate:[202605010000 TO 202605182359]"
    )


@pytest.mark.anyio
async def test_arxiv_collector_retries_failures() -> None:
    class FlakyClient:
        def __init__(self) -> None:
            self.calls = 0

        def results(self, search: object) -> list[object]:
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary failure")
            return [FakeArxivResult()]

    flaky_client = FlakyClient()
    collector = ArxivCollector(
        config=CollectorConfig(max_retries=2),
        client=flaky_client,
        search_factory=fake_search_factory,
    )

    items = await collector.collect(query="ai", max_results=1)

    assert len(items) == 1
    assert flaky_client.calls == 2
