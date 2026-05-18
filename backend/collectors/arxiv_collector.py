from __future__ import annotations

import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Any

import requests

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.proxy import collector_proxy_config


logger = logging.getLogger(__name__)


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_ARXIV_TIMEOUT_SECONDS = 120.0
USER_AGENT = "multi-agent-intel/0.1 (+https://github.com/Hbw1201/research-intelligence-agent)"


class ArxivCollector(BaseCollector):
    """Collect and normalize arXiv search results via the public Atom API."""

    name = "arxiv"

    def __init__(
        self,
        config: CollectorConfig | None = None,
        client: Any | None = None,
        search_factory: Any | None = None,
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
        """Collect arXiv results for a keyword query."""
        normalized_query = self._build_query(query, start_date, end_date)
        if not normalized_query or max_results <= 0:
            return []

        if self.config.rate_limit_delay_seconds > 0:
            await asyncio.sleep(self.config.rate_limit_delay_seconds)

        last_error: Exception | None = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Collecting arXiv results", extra={"query": normalized_query, "attempt": attempt})
                xml_text = await asyncio.wait_for(
                    asyncio.to_thread(self._request_atom_feed, normalized_query, max_results),
                    timeout=self._request_timeout_seconds() + 5,
                )
                return self._parse_atom_feed(xml_text)[:max_results]
            except Exception as exc:  # noqa: BLE001 - retries intentionally catch client/network errors.
                last_error = exc
                logger.warning(
                    "arXiv collection attempt failed",
                    extra={"query": normalized_query, "attempt": attempt, "max_attempts": attempts},
                    exc_info=True,
                )
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))

        raise RuntimeError("arXiv collection failed") from last_error

    def _request_atom_feed(self, query: str, max_results: int) -> str:
        params = {
            "search_query": query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        response = requests.get(
            ARXIV_API_URL,
            params=params,
            headers={"User-Agent": USER_AGENT},
            proxies=collector_proxy_config(self.config).requests_proxies(),
            timeout=self._request_timeout_seconds(),
        )
        response.raise_for_status()
        return response.text

    def _request_timeout_seconds(self) -> float:
        for value in (
            self.config.arxiv_timeout_seconds,
            self.config.collector_timeout_seconds,
            DEFAULT_ARXIV_TIMEOUT_SECONDS,
        ):
            if value is not None and value > 0:
                return float(value)
        return DEFAULT_ARXIV_TIMEOUT_SECONDS

    @classmethod
    def _parse_atom_feed(cls, xml_text: str) -> list[ResearchItem]:
        root = ET.fromstring(xml_text)
        return [cls._normalize_entry(entry) for entry in root.findall("atom:entry", ATOM_NS)]

    @classmethod
    def _normalize_entry(cls, entry: ET.Element) -> ResearchItem:
        title = cls._clean_text(cls._node_text(entry.find("atom:title", ATOM_NS)))
        abstract = cls._clean_text(cls._node_text(entry.find("atom:summary", ATOM_NS))) or None
        published_at = cls._parse_datetime(cls._node_text(entry.find("atom:published", ATOM_NS)))
        updated_at = cls._parse_datetime(cls._node_text(entry.find("atom:updated", ATOM_NS)))
        url = cls._entry_url(entry)
        arxiv_id = cls._arxiv_id(cls._node_text(entry.find("atom:id", ATOM_NS)) or url)
        categories = cls._categories(entry)
        primary_category = cls._primary_category(entry) or (categories[0] if categories else None)
        pdf_url = cls._link_href(entry, title="pdf") or cls._link_href(entry, link_type="application/pdf")

        metadata: dict[str, Any] = {
            "arxiv_id": arxiv_id,
            "primary_category": primary_category,
            "categories": categories,
        }
        if pdf_url:
            metadata["pdf_url"] = pdf_url
        if updated_at:
            metadata["updated_at"] = updated_at.isoformat()
        doi = cls._node_text(entry.find("arxiv:doi", ATOM_NS))
        if doi:
            metadata["doi"] = doi
        journal_ref = cls._node_text(entry.find("arxiv:journal_ref", ATOM_NS))
        if journal_ref:
            metadata["journal_ref"] = journal_ref
        comment = cls._node_text(entry.find("arxiv:comment", ATOM_NS))
        if comment:
            metadata["comment"] = comment

        return ResearchItem(
            title=title,
            abstract=abstract,
            url=url or f"https://arxiv.org/abs/{arxiv_id}",
            source_name="arxiv",
            source_type="paper",
            item_type="paper",
            authors=cls._authors(entry),
            published_at=published_at,
            raw_text="\n\n".join(part for part in [title, abstract] if part),
            external_id=arxiv_id,
            keywords=categories,
            metadata=metadata,
        )

    @classmethod
    def _entry_url(cls, entry: ET.Element) -> str:
        alternate = cls._link_href(entry, rel="alternate")
        if alternate:
            return alternate
        return cls._node_text(entry.find("atom:id", ATOM_NS))

    @staticmethod
    def _link_href(
        entry: ET.Element,
        rel: str | None = None,
        title: str | None = None,
        link_type: str | None = None,
    ) -> str | None:
        for link in entry.findall("atom:link", ATOM_NS):
            if rel is not None and link.attrib.get("rel") != rel:
                continue
            if title is not None and link.attrib.get("title") != title:
                continue
            if link_type is not None and link.attrib.get("type") != link_type:
                continue
            href = link.attrib.get("href")
            if href:
                return href
        return None

    @staticmethod
    def _authors(entry: ET.Element) -> list[str]:
        authors: list[str] = []
        for author in entry.findall("atom:author", ATOM_NS):
            name = ArxivCollector._clean_text(ArxivCollector._node_text(author.find("atom:name", ATOM_NS)))
            if name:
                authors.append(name)
        return authors

    @staticmethod
    def _categories(entry: ET.Element) -> list[str]:
        categories: list[str] = []
        for category in entry.findall("atom:category", ATOM_NS):
            term = category.attrib.get("term")
            if term:
                categories.append(term)
        return categories

    @staticmethod
    def _primary_category(entry: ET.Element) -> str | None:
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        if primary is None:
            return None
        return primary.attrib.get("term")

    @staticmethod
    def _node_text(node: ET.Element | None) -> str:
        if node is None:
            return ""
        return "".join(node.itertext())

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        value = value.strip()
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _arxiv_id(value: str | None) -> str | None:
        if not value:
            return None
        return str(value).rstrip("/").split("/")[-1]

    @classmethod
    def _build_query(cls, query: str, start_date: date | None, end_date: date | None) -> str:
        base_query = cls._clean_text(query)
        if not base_query:
            return ""
        search_query = base_query if ":" in base_query else f"all:{base_query}"
        if start_date is None and end_date is None:
            return search_query

        start = cls._format_arxiv_date(start_date, "0000") if start_date else "*"
        end = cls._format_arxiv_date(end_date, "2359") if end_date else "*"
        return f"({search_query}) AND submittedDate:[{start} TO {end}]"

    @staticmethod
    def _format_arxiv_date(value: date, time_suffix: str) -> str:
        return f"{value:%Y%m%d}{time_suffix}"
