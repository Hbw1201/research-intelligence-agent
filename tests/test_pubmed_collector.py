from datetime import date, datetime, timezone
from typing import Any

import pytest

from backend.collectors.base import CollectorConfig
from backend.collectors.pubmed_collector import PubMedCollector


PUBMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>12345</PMID>
      <Article>
        <Journal>
          <JournalIssue>
            <PubDate>
              <Year>2026</Year>
              <Month>May</Month>
              <Day>18</Day>
            </PubDate>
          </JournalIssue>
          <Title>Journal of Useful Tests</Title>
        </Journal>
        <ArticleTitle>  Test   PubMed Article  </ArticleTitle>
        <Abstract>
          <AbstractText>First abstract sentence.</AbstractText>
          <AbstractText>Second abstract sentence.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><ForeName>Ada</ForeName><LastName>Lovelace</LastName></Author>
          <Author><CollectiveName>Example Consortium</CollectiveName></Author>
        </AuthorList>
      </Article>
      <MeshHeadingList>
        <MeshHeading><DescriptorName>Machine Learning</DescriptorName></MeshHeading>
      </MeshHeadingList>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="doi">10.1234/pubmed-test</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>67890</PMID>
      <Article>
        <Journal>
          <JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue>
        </Journal>
        <ArticleTitle>Second Article</ArticleTitle>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


class FakeResponse:
    def __init__(self, json_data: dict[str, Any] | None = None, text: str = "") -> None:
        self._json_data = json_data or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        return None


class FakePubMedClient:
    def __init__(self, ids: list[str], xml_text: str = PUBMED_XML) -> None:
        self.ids = ids
        self.xml_text = xml_text
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if "esearch.fcgi" in url:
            return FakeResponse({"esearchresult": {"idlist": self.ids}})
        return FakeResponse(text=self.xml_text)


class FakeAsyncClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"esearchresult": {"idlist": []}})


@pytest.mark.anyio
async def test_pubmed_collector_empty_results() -> None:
    client = FakePubMedClient(ids=[])
    collector = PubMedCollector(client=client)

    items = await collector.collect(query="cancer immunotherapy", max_results=5)

    assert items == []
    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_pubmed_collector_normalizes_result() -> None:
    collector = PubMedCollector(client=FakePubMedClient(ids=["12345"]))

    items = await collector.collect(query="machine learning", max_results=1)

    assert len(items) == 1
    item = items[0]
    assert item.title == "Test PubMed Article"
    assert item.abstract == "First abstract sentence. Second abstract sentence."
    assert item.url == "https://pubmed.ncbi.nlm.nih.gov/12345/"
    assert item.source_name == "pubmed"
    assert item.source_type == "paper"
    assert item.item_type == "paper"
    assert item.authors == ["Ada Lovelace", "Example Consortium"]
    assert item.published_at == datetime(2026, 5, 18, tzinfo=timezone.utc)
    assert item.external_id == "12345"
    assert item.keywords == ["Machine Learning"]
    assert item.metadata["journal"] == "Journal of Useful Tests"
    assert item.metadata["doi"] == "10.1234/pubmed-test"


@pytest.mark.anyio
async def test_pubmed_collector_max_results_and_date_params() -> None:
    client = FakePubMedClient(ids=["12345", "67890", "11111"])
    collector = PubMedCollector(client=client)

    items = await collector.collect(
        query="genomics",
        max_results=2,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 18),
    )

    assert len(items) == 2
    search_params = client.calls[0]["params"]
    assert search_params["retmax"] == 2
    assert search_params["mindate"] == "2026/05/01"
    assert search_params["maxdate"] == "2026/05/18"
    assert search_params["datetype"] == "pdat"
    assert client.calls[1]["params"]["id"] == "12345,67890"


@pytest.mark.anyio
async def test_pubmed_collector_uses_explicit_proxy_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.pubmed_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = PubMedCollector(config=CollectorConfig(proxy="http://127.0.0.1:7897"))

    items = await collector.collect(query="single cell", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [
        {
            "timeout": 20.0,
            "proxy": "http://127.0.0.1:7897",
            "trust_env": False,
        }
    ]


@pytest.mark.anyio
async def test_pubmed_collector_preserves_default_client_behavior_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.pubmed_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = PubMedCollector(config=CollectorConfig())

    items = await collector.collect(query="single cell", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [{"timeout": 20.0}]
