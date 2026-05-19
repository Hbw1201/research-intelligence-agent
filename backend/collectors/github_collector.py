from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime
from typing import Any

import httpx

from backend.collectors.base import BaseCollector, CollectorConfig, ResearchItem
from backend.collectors.errors import log_collector_attempt_failure, should_retry_collector_error
from backend.collectors.proxy import collector_proxy_config


logger = logging.getLogger(__name__)


class GitHubCollector(BaseCollector):
    """Collect and normalize GitHub repositories."""

    name = "github"
    search_url = "https://api.github.com/search/repositories"

    def __init__(
        self,
        config: CollectorConfig | None = None,
        client: httpx.AsyncClient | Any | None = None,
        token: str | None = None,
    ) -> None:
        super().__init__(config or CollectorConfig())
        self._client = client
        self._token = token

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Search GitHub repositories by keyword query."""
        query = self._build_query(query, start_date, end_date)
        if not query or max_results <= 0:
            return []

        if self.config.rate_limit_delay_seconds > 0:
            await asyncio.sleep(self.config.rate_limit_delay_seconds)

        last_error: Exception | None = None
        attempts = max(1, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                logger.info("Collecting GitHub repositories", extra={"query": query, "attempt": attempt})
                return await asyncio.wait_for(
                    self._fetch_items(query, max_results),
                    timeout=self.config.timeout_seconds,
                )
            except Exception as exc:  # noqa: BLE001 - retry network and parse failures.
                last_error = exc
                log_collector_attempt_failure(
                    logger,
                    "GitHub collection attempt failed",
                    exc,
                    extra={"query": query, "attempt": attempt, "max_attempts": attempts},
                )
                if attempt < attempts and should_retry_collector_error(exc):
                    await asyncio.sleep(min(2 ** (attempt - 1), 8))
                    continue
                break

        raise RuntimeError("GitHub collection failed") from last_error

    async def _fetch_items(self, query: str, max_results: int) -> list[ResearchItem]:
        async def fetch(client: Any) -> list[ResearchItem]:
            response = await client.get(
                self.search_url,
                params={
                    "q": query,
                    "per_page": max(1, min(max_results, 100)),
                    "sort": "updated",
                    "order": "desc",
                },
                headers=self._headers(),
            )
            self._raise_for_status(response)
            repos = response.json().get("items", [])[:max_results]
            return [self._normalize_repo(repo) for repo in repos]

        return await self._with_client(fetch)

    async def _with_client(self, work: Any) -> Any:
        if self._client is not None:
            return await work(self._client)

        client_kwargs: dict[str, Any] = {"timeout": self.config.timeout_seconds}
        client_kwargs.update(collector_proxy_config(self.config).httpx_client_kwargs())

        async with httpx.AsyncClient(**client_kwargs) as client:
            return await work(client)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "multi-agent-intel",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @classmethod
    def _normalize_repo(cls, repo: dict[str, Any]) -> ResearchItem:
        owner = repo.get("owner") or {}
        owner_name = owner.get("login")
        full_name = repo.get("full_name") or repo.get("name") or ""
        description = cls._clean_text(repo.get("description"))
        topics = list(repo.get("topics") or [])
        language = repo.get("language")
        updated_at = cls._parse_datetime(repo.get("updated_at"))

        metadata = {
            "owner": owner_name,
            "stars": repo.get("stargazers_count", 0),
            "updated_at": repo.get("updated_at"),
            "language": language,
            "topics": topics,
            "forks": repo.get("forks_count", 0),
        }

        keywords = [topic for topic in topics if topic]
        if language:
            keywords.append(str(language))

        return ResearchItem(
            title=str(full_name),
            abstract=description or None,
            url=str(repo.get("html_url") or ""),
            source_name="github",
            source_type="code",
            item_type="repository",
            authors=[str(owner_name)] if owner_name else [],
            published_at=updated_at,
            raw_text="\n\n".join(part for part in [str(full_name), description] if part),
            external_id=str(repo.get("id") or full_name),
            keywords=keywords,
            metadata=metadata,
        )

    @classmethod
    def _build_query(cls, query: str, start_date: date | None, end_date: date | None) -> str:
        query = cls._clean_text(query)
        if not query:
            return ""
        qualifiers: list[str] = []
        if start_date is not None and end_date is not None:
            qualifiers.append(f"pushed:{start_date.isoformat()}..{end_date.isoformat()}")
        elif start_date is not None:
            qualifiers.append(f"pushed:>={start_date.isoformat()}")
        elif end_date is not None:
            qualifiers.append(f"pushed:<={end_date.isoformat()}")
        return " ".join([query, *qualifiers])

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _clean_text(value: str | None) -> str:
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _raise_for_status(response: Any) -> None:
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
