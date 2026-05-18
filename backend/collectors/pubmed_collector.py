from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from typing import Any

import httpx

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.proxy import collector_proxy_config


logger = logging.getLogger(__name__)


class PubMedCollector(BaseCollector):
    """Collect and normalize PubMed articles."""

    name = "pubmed"
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(
        self,
        config: CollectorConfig | None = None,
        client: httpx.AsyncClient | Any | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self._client = client

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Collect PubMed articles for a keyword query."""
        query = self._clean_text(query)
        if not query or max_results <= 0:
            return []

        if self.config.rate_limit_delay_seconds > 0:
            await asyncio.sleep(self.config.rate_limit_delay_seconds)

        last_error: Exception | None = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Collecting PubMed results", extra={"query": query, "attempt": attempt})
                return await asyncio.wait_for(
                    self._fetch_items(query, max_results, start_date, end_date),
                    timeout=self.config.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - retry network and parse failures.
                last_error = exc
                logger.warning(
                    "PubMed collection attempt failed",
                    extra={"query": query, "attempt": attempt, "max_attempts": attempts},
                    exc_info=True,
                )
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))

        raise RuntimeError("PubMed collection failed") from last_error

    async def _fetch_items(
        self,
        query: str,
        max_results: int,
        start_date: date | None,
        end_date: date | None,
    ) -> list[ResearchItem]:
        async def fetch(client: Any) -> list[ResearchItem]:
            search_response = await client.get(
                self.search_url,
                params=self._search_params(query, max_results, start_date, end_date),
            )
            self._raise_for_status(search_response)
            ids = search_response.json().get("esearchresult", {}).get("idlist", [])[:max_results]
            if not ids:
                return []

            fetch_response = await client.get(
                self.fetch_url,
                params={
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "xml",
                },
            )
            self._raise_for_status(fetch_response)
            return self._parse_articles(fetch_response.text)[:max_results]

        return await self._with_client(fetch)

    async def _with_client(self, work: Any) -> Any:
        if self._client is not None:
            return await work(self._client)

        client_kwargs: dict[str, Any] = {"timeout": self.config.timeout_seconds}
        client_kwargs.update(collector_proxy_config(self.config).httpx_client_kwargs())

        async with httpx.AsyncClient(**client_kwargs) as client:
            return await work(client)

    @staticmethod
    def _search_params(
        query: str,
        max_results: int,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "pub_date",
        }
        if start_date is not None or end_date is not None:
            params["datetype"] = "pdat"
        if start_date is not None:
            params["mindate"] = f"{start_date:%Y/%m/%d}"
        if end_date is not None:
            params["maxdate"] = f"{end_date:%Y/%m/%d}"
        return params

    @classmethod
    def _parse_articles(cls, xml_text: str) -> list[ResearchItem]:
        root = ET.fromstring(xml_text)
        items: list[ResearchItem] = []
        for article_node in root.findall(".//PubmedArticle"):
            pmid = cls._node_text(article_node.find(".//PMID"))
            title = cls._node_text(article_node.find(".//ArticleTitle"))
            abstract = cls._abstract(article_node)
            authors = cls._authors(article_node)
            published_at = cls._published_at(article_node)
            journal = cls._node_text(article_node.find(".//Journal/Title"))
            doi = cls._article_id(article_node, "doi")
            keywords = cls._mesh_terms(article_node)

            metadata: dict[str, Any] = {}
            if journal:
                metadata["journal"] = journal
            if doi:
                metadata["doi"] = doi

            items.append(
                ResearchItem(
                    title=title,
                    abstract=abstract,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    source_name="pubmed",
                    source_type="paper",
                    item_type="paper",
                    authors=authors,
                    published_at=published_at,
                    raw_text="\n\n".join(part for part in [title, abstract] if part),
                    external_id=pmid,
                    keywords=keywords,
                    metadata=metadata,
                )
            )
        return items

    @classmethod
    def _abstract(cls, article_node: ET.Element) -> str | None:
        parts = [cls._node_text(node) for node in article_node.findall(".//Abstract/AbstractText")]
        abstract = cls._clean_text(" ".join(part for part in parts if part))
        return abstract or None

    @classmethod
    def _authors(cls, article_node: ET.Element) -> list[str]:
        authors: list[str] = []
        for author_node in article_node.findall(".//AuthorList/Author"):
            collective = cls._node_text(author_node.find("CollectiveName"))
            if collective:
                authors.append(collective)
                continue

            fore_name = cls._node_text(author_node.find("ForeName"))
            last_name = cls._node_text(author_node.find("LastName"))
            name = cls._clean_text(" ".join(part for part in [fore_name, last_name] if part))
            if name:
                authors.append(name)
        return authors

    @classmethod
    def _published_at(cls, article_node: ET.Element) -> datetime | None:
        pub_date = article_node.find(".//JournalIssue/PubDate")
        if pub_date is None:
            return None

        year = cls._node_text(pub_date.find("Year"))
        if not year:
            medline_date = cls._node_text(pub_date.find("MedlineDate"))
            year_match = re.search(r"\d{4}", medline_date)
            year = year_match.group(0) if year_match else ""
        if not year:
            return None

        month = cls._month_number(cls._node_text(pub_date.find("Month")))
        day_text = cls._node_text(pub_date.find("Day"))
        day = int(day_text) if day_text.isdigit() else 1
        return datetime(int(year), month, day, tzinfo=timezone.utc)

    @classmethod
    def _mesh_terms(cls, article_node: ET.Element) -> list[str]:
        return [
            term
            for term in (cls._node_text(node) for node in article_node.findall(".//MeshHeading/DescriptorName"))
            if term
        ]

    @classmethod
    def _article_id(cls, article_node: ET.Element, id_type: str) -> str | None:
        for node in article_node.findall(".//ArticleId"):
            if node.attrib.get("IdType") == id_type:
                return cls._node_text(node)
        return None

    @classmethod
    def _node_text(cls, node: ET.Element | None) -> str:
        if node is None:
            return ""
        return cls._clean_text("".join(node.itertext()))

    @staticmethod
    def _month_number(value: str) -> int:
        months = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        if value.isdigit():
            return max(1, min(int(value), 12))
        return months.get(value[:3].lower(), 1)

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
