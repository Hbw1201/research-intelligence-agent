from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, time, timezone
from email.utils import parsedate_to_datetime
from time import struct_time
from typing import Any

import httpx

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.proxy import collector_proxy_config


logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """Collect and normalize entries from a configured RSS/Atom feed."""

    name = "rss"

    def __init__(
        self,
        feed_url: str,
        config: CollectorConfig | None = None,
        client: httpx.AsyncClient | Any | None = None,
        parser: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self.feed_url = feed_url
        self._client = client
        self._parser = parser

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Collect feed entries matching the optional keyword query."""
        query = self._clean_text(query).lower()
        if not self.feed_url or max_results <= 0:
            return []

        if self.config.rate_limit_delay_seconds > 0:
            await asyncio.sleep(self.config.rate_limit_delay_seconds)

        last_error: Exception | None = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Collecting RSS entries", extra={"feed_url": self.feed_url, "attempt": attempt})
                return await asyncio.wait_for(
                    self._fetch_items(query, max_results, start_date, end_date),
                    timeout=self.config.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - retry network and parse failures.
                last_error = exc
                logger.warning(
                    "RSS collection attempt failed",
                    extra={"feed_url": self.feed_url, "attempt": attempt, "max_attempts": attempts},
                    exc_info=True,
                )
                if attempt < attempts:
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))

        raise RuntimeError("RSS collection failed") from last_error

    async def _fetch_items(
        self,
        query: str,
        max_results: int,
        start_date: date | None,
        end_date: date | None,
    ) -> list[ResearchItem]:
        async def fetch(client: Any) -> list[ResearchItem]:
            response = await client.get(self.feed_url)
            self._raise_for_status(response)
            parsed_feed = self._parse_feed(response.text)
            feed_title = self._get(self._get(parsed_feed, "feed", {}), "title", "rss")

            items: list[ResearchItem] = []
            for entry in self._get(parsed_feed, "entries", []):
                item = self._normalize_entry(entry, feed_title)
                if query and query not in f"{item.title} {item.abstract or ''}".lower():
                    continue
                if not self._inside_date_range(item.published_at, start_date, end_date):
                    continue
                items.append(item)
                if len(items) >= max_results:
                    break
            return items

        return await self._with_client(fetch)

    async def _with_client(self, work: Any) -> Any:
        if self._client is not None:
            return await work(self._client)

        client_kwargs: dict[str, Any] = {"timeout": self.config.timeout_seconds}
        client_kwargs.update(collector_proxy_config(self.config).httpx_client_kwargs())

        async with httpx.AsyncClient(**client_kwargs) as client:
            return await work(client)

    def _parse_feed(self, text: str) -> Any:
        if self._parser is not None:
            return self._parser(text)

        try:
            import feedparser
        except ImportError as exc:  # pragma: no cover - dependency is installed in normal runtime.
            raise RuntimeError("Install the 'feedparser' package to use RSSCollector.") from exc
        return feedparser.parse(text)

    def _normalize_entry(self, entry: Any, feed_title: str) -> ResearchItem:
        title = self._clean_text(self._get(entry, "title", ""))
        summary = self._clean_text(self._get(entry, "summary", self._get(entry, "description", ""))) or None
        url = self._get(entry, "link", "")
        published_at = self._entry_datetime(entry)
        authors = self._authors(entry)
        external_id = self._get(entry, "id", None) or self._get(entry, "guid", None) or url

        return ResearchItem(
            title=title,
            abstract=summary,
            url=str(url),
            source_name=str(feed_title or "rss"),
            source_type="news",
            item_type="feed_entry",
            authors=authors,
            published_at=published_at,
            raw_text="\n\n".join(part for part in [title, summary] if part),
            external_id=str(external_id) if external_id else None,
            keywords=[],
            metadata={"feed_url": self.feed_url},
        )

    @classmethod
    def _authors(cls, entry: Any) -> list[str]:
        raw_authors = cls._get(entry, "authors", None)
        if isinstance(raw_authors, list):
            authors = [cls._get(author, "name", str(author)) for author in raw_authors]
            return [cls._clean_text(str(author)) for author in authors if cls._clean_text(str(author))]

        author = cls._get(entry, "author", None)
        if author:
            return [cls._clean_text(str(author))]
        return []

    @classmethod
    def _entry_datetime(cls, entry: Any) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            parsed = cls._get(entry, key, None)
            if isinstance(parsed, struct_time):
                return datetime(*parsed[:6], tzinfo=timezone.utc)

        for key in ("published", "updated"):
            value = cls._get(entry, key, None)
            if value:
                parsed_datetime = parsedate_to_datetime(str(value))
                if parsed_datetime.tzinfo is None:
                    return parsed_datetime.replace(tzinfo=timezone.utc)
                return parsed_datetime
        return None

    @staticmethod
    def _inside_date_range(
        published_at: datetime | None,
        start_date: date | None,
        end_date: date | None,
    ) -> bool:
        if published_at is None:
            return True
        if start_date is not None and published_at < datetime.combine(start_date, time.min, timezone.utc):
            return False
        if end_date is not None and published_at > datetime.combine(end_date, time.max, timezone.utc):
            return False
        return True

    @staticmethod
    def _get(source: Any, key: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
