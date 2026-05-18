from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.proxy import collector_proxy_config


logger = logging.getLogger(__name__)


class ArxivCollector(BaseCollector):
    """Collect and normalize arXiv search results."""

    name = "arxiv"

    def __init__(
        self,
        config: CollectorConfig | None = None,
        client: Any | None = None,
        search_factory: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self._client = client
        self._search_factory = search_factory

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
                results = await asyncio.wait_for(
                    asyncio.to_thread(self._fetch_results, normalized_query, max_results),
                    timeout=self.config.timeout_seconds,
                )
                return [self._normalize_result(result) for result in results[:max_results]]
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

    def _fetch_results(self, query: str, max_results: int) -> list[Any]:
        search = self._create_search(query=query, max_results=max_results)
        return list(self._get_client(max_results).results(search))

    def _get_client(self, max_results: int) -> Any:
        if self._client is not None:
            self._apply_proxy_to_client(self._client)
            return self._client

        arxiv = self._import_arxiv()
        self._client = arxiv.Client(
            page_size=max(1, min(max_results, 100)),
            delay_seconds=max(self.config.rate_limit_delay_seconds, 0.0),
            num_retries=max(0, self.config.max_retries - 1),
        )
        self._apply_proxy_to_client(self._client)
        return self._client

    def _apply_proxy_to_client(self, client: Any) -> None:
        session = getattr(client, "_session", None)
        if session is not None:
            collector_proxy_config(self.config).apply_requests_session(session)

    def _create_search(self, query: str, max_results: int) -> Any:
        if self._search_factory is not None:
            return self._search_factory(query=query, max_results=max_results)

        arxiv = self._import_arxiv()
        return arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
        )

    @staticmethod
    def _import_arxiv() -> Any:
        try:
            import arxiv
        except ImportError as exc:  # pragma: no cover - dependency is installed in normal runtime.
            raise RuntimeError("Install the 'arxiv' package to use ArxivCollector.") from exc
        return arxiv

    @classmethod
    def _normalize_result(cls, result: Any) -> ResearchItem:
        title = cls._clean_text(getattr(result, "title", ""))
        abstract = cls._clean_text(getattr(result, "summary", "")) or None
        external_id = cls._external_id(result)
        url = getattr(result, "entry_id", None) or f"https://arxiv.org/abs/{external_id}"
        authors = [str(getattr(author, "name", author)).strip() for author in getattr(result, "authors", [])]
        authors = [author for author in authors if author]
        categories = list(getattr(result, "categories", []) or [])
        primary_category = getattr(result, "primary_category", None)

        metadata: dict[str, Any] = {
            "primary_category": primary_category,
            "categories": categories,
        }
        for attr in ("doi", "journal_ref", "comment"):
            value = getattr(result, attr, None)
            if value:
                metadata[attr] = value

        updated = getattr(result, "updated", None)
        if isinstance(updated, datetime):
            metadata["updated_at"] = updated.isoformat()

        return ResearchItem(
            title=title,
            abstract=abstract,
            url=str(url),
            source_name="arxiv",
            source_type="paper",
            item_type="paper",
            authors=authors,
            published_at=getattr(result, "published", None),
            raw_text="\n\n".join(part for part in [title, abstract] if part),
            external_id=external_id,
            keywords=categories,
            metadata=metadata,
        )

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _external_id(result: Any) -> str | None:
        get_short_id = getattr(result, "get_short_id", None)
        if callable(get_short_id):
            return str(get_short_id())

        entry_id = getattr(result, "entry_id", None)
        if not entry_id:
            return None
        return str(entry_id).rstrip("/").split("/")[-1]

    @classmethod
    def _build_query(cls, query: str, start_date: date | None, end_date: date | None) -> str:
        base_query = cls._clean_text(query)
        if not base_query:
            return ""
        if start_date is None and end_date is None:
            return base_query

        start = cls._format_arxiv_date(start_date, "0000") if start_date else "*"
        end = cls._format_arxiv_date(end_date, "2359") if end_date else "*"
        return f"({base_query}) AND submittedDate:[{start} TO {end}]"

    @staticmethod
    def _format_arxiv_date(value: date, time_suffix: str) -> str:
        return f"{value:%Y%m%d}{time_suffix}"
