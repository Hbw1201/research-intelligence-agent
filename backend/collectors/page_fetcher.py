from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx

from backend.collectors.base import CollectorConfig
from backend.collectors.proxy import collector_proxy_config
from backend.config import Settings, get_settings


logger = logging.getLogger(__name__)


ALLOWED_CONTENT_TYPES = ("text/html", "text/plain", "application/xhtml+xml")
BINARY_CONTENT_TYPES = (
    "application/octet-stream",
    "application/pdf",
    "application/zip",
    "image/",
)
EXPECTED_SKIP_STATUSES = {401, 403, 404, 429}
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)


@dataclass(frozen=True)
class FetchedPage:
    """Fetched page content accepted for MVP extraction."""

    url: str
    content: str
    content_type: str | None = None


@dataclass(frozen=True)
class PageFetchResult:
    """Structured result for a single page fetch attempt."""

    status: str
    page: FetchedPage | None = None
    reason: str | None = None
    status_code: int | None = None


class PageFetcher:
    """Bounded page fetcher for single-page web discovery."""

    def __init__(
        self,
        settings: Settings | None = None,
        config: CollectorConfig | None = None,
        http_client: httpx.AsyncClient | Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.config = config or CollectorConfig()
        self._http_client = http_client

    async def fetch(self, url: str) -> PageFetchResult:
        """Fetch one safe text-like page, returning a structured skip reason when blocked."""
        try:
            response = await self._get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in EXPECTED_SKIP_STATUSES:
                reason = f"skipped_{status_code}"
                logger.info(
                    "Page fetch skipped status=%s url=%s",
                    status_code,
                    url,
                    extra={"url": url, "status_code": status_code, "page_fetch_status": reason},
                )
                return PageFetchResult(status=reason, reason=reason, status_code=status_code)
            logger.warning("Page fetch failed", extra={"url": url, "status_code": status_code}, exc_info=True)
            return PageFetchResult(status="failed_http", reason="failed_http", status_code=status_code)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("Page fetch failed", extra={"url": url}, exc_info=True)
            return PageFetchResult(status="failed", reason=exc.__class__.__name__)

        content_type = self._content_type(response)
        if self._is_binary_content_type(content_type) or not self._is_allowed_content_type(content_type):
            return PageFetchResult(status="skipped_content_type", reason="skipped_content_type")

        content = response.content[: self.settings.web_page_max_bytes]
        text = content.decode(response.encoding or "utf-8", errors="replace")
        return PageFetchResult(
            status="fetched",
            page=FetchedPage(url=str(response.url), content=text, content_type=content_type),
        )

    async def _get(self, url: str) -> httpx.Response:
        timeout = self.settings.web_page_timeout_seconds
        headers = {"User-Agent": DEFAULT_USER_AGENT}
        if self._http_client is not None:
            return await self._http_client.get(url, timeout=timeout, follow_redirects=True, headers=headers)

        client_kwargs: dict[str, Any] = {"timeout": timeout, "follow_redirects": True}
        client_kwargs.update(collector_proxy_config(self.config).httpx_client_kwargs())
        async with httpx.AsyncClient(**client_kwargs) as client:
            return await client.get(url, headers=headers)

    @staticmethod
    def _content_type(response: httpx.Response) -> str | None:
        value = response.headers.get("content-type")
        return value.split(";", 1)[0].strip().lower() if value else None

    @staticmethod
    def _is_allowed_content_type(content_type: str | None) -> bool:
        if not content_type:
            return True
        return any(content_type.startswith(allowed) for allowed in ALLOWED_CONTENT_TYPES)

    @staticmethod
    def _is_binary_content_type(content_type: str | None) -> bool:
        if not content_type:
            return False
        return any(content_type.startswith(binary) for binary in BINARY_CONTENT_TYPES)
