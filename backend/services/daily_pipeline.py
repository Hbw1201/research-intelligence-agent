from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from backend.collectors.base import ResearchItem
from backend.services.digest_service import DigestItem
from backend.services.ranking_service import RankedItem, RelevanceRankingService


class CollectorProtocol(Protocol):
    """Collector interface used by the manual daily pipeline."""

    name: str

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ResearchItem]:
        """Collect normalized research items."""


class DigestServiceProtocol(Protocol):
    """Digest service interface used by the manual daily pipeline."""

    async def summarize_items(
        self,
        items: list[ResearchItem],
        user_profile: str | None = None,
        max_items: int = 10,
    ) -> list[DigestItem]:
        """Summarize ranked items."""

    def format_daily_digest(self, digests: list[DigestItem], title: str = "Daily Research Intelligence") -> str:
        """Format a markdown report."""


@dataclass(frozen=True)
class DailyPipelineResult:
    """Structured result for the manual daily intelligence run."""

    collected_items: list[ResearchItem]
    unique_items: list[ResearchItem]
    ranked_items: list[RankedItem]
    digests: list[DigestItem]
    report: str
    output_path: Path | None = None


@dataclass(frozen=True)
class DailyPipelineOptions:
    """Manual daily pipeline input options."""

    keywords: list[str]
    user_profile: str | None = None
    max_items: int = 10
    sources: list[str] = field(default_factory=list)
    output_path: str | Path | None = None


class DailyIntelligencePipeline:
    """Manual collect-rank-digest pipeline with no scheduler or database dependency."""

    def __init__(
        self,
        collectors: dict[str, CollectorProtocol],
        digest_service: DigestServiceProtocol,
        ranking_service: RelevanceRankingService | None = None,
        candidate_pool_multiplier: int = 5,
    ) -> None:
        self.collectors = {name.strip().lower(): collector for name, collector in collectors.items()}
        self.digest_service = digest_service
        self.ranking_service = ranking_service or RelevanceRankingService()
        self.candidate_pool_multiplier = max(1, candidate_pool_multiplier)

    async def run(
        self,
        keywords: list[str],
        user_profile: str | None = None,
        max_items: int = 10,
        sources: list[str] | None = None,
        output_path: str | Path | None = None,
    ) -> DailyPipelineResult:
        """Collect, deduplicate, rank, digest, format, and optionally save a daily report."""
        options = DailyPipelineOptions(
            keywords=self._normalize_keywords(keywords),
            user_profile=user_profile,
            max_items=max_items,
            sources=self._normalize_sources(sources),
            output_path=output_path,
        )
        if not options.keywords:
            raise ValueError("At least one keyword is required.")
        if options.max_items <= 0:
            raise ValueError("max_items must be greater than zero.")

        selected_sources = options.sources or list(self.collectors.keys())
        query = " ".join(options.keywords)
        collection_limit = options.max_items * self.candidate_pool_multiplier
        collected_items = await self._collect_items(query, collection_limit, selected_sources)
        unique_items = self.deduplicate_items(collected_items)
        ranked_items = self.ranking_service.rank_items(
            unique_items,
            user_profile=options.user_profile,
            keywords=options.keywords,
            max_items=options.max_items,
        )
        top_items = [ranked.item for ranked in ranked_items]
        digests = await self.digest_service.summarize_items(
            top_items,
            user_profile=options.user_profile,
            max_items=options.max_items,
        )
        report = self.format_report(options.keywords, digests)
        saved_path = self.save_report(report, options.output_path) if options.output_path else None

        return DailyPipelineResult(
            collected_items=collected_items,
            unique_items=unique_items,
            ranked_items=ranked_items,
            digests=digests,
            report=report,
            output_path=saved_path,
        )

    async def _collect_items(self, query: str, max_items: int, sources: list[str]) -> list[ResearchItem]:
        collected_items: list[ResearchItem] = []
        for source in sources:
            collector = self.collectors.get(source)
            if collector is None:
                raise ValueError(f"Unknown collector source: {source}")
            collected_items.extend(await collector.collect(query=query, max_results=max_items))
        return collected_items

    @staticmethod
    def deduplicate_items(items: list[ResearchItem]) -> list[ResearchItem]:
        """Merge items by normalized URL or external_id while preserving first occurrence."""
        seen_urls: set[str] = set()
        seen_external_ids: set[str] = set()
        unique_items: list[ResearchItem] = []

        for item in items:
            url_key = DailyIntelligencePipeline._normalize_url(item.url)
            external_id_key = DailyIntelligencePipeline._normalize_external_id(item.external_id)
            if url_key and url_key in seen_urls:
                continue
            if external_id_key and external_id_key in seen_external_ids:
                continue

            unique_items.append(item)
            if url_key:
                seen_urls.add(url_key)
            if external_id_key:
                seen_external_ids.add(external_id_key)

        return unique_items

    def format_report(self, keywords: list[str], digests: list[DigestItem]) -> str:
        """Format the final markdown daily report through the digest service."""
        topic = ", ".join(keywords)
        title = f"Daily Research Intelligence - {topic}" if topic else "Daily Research Intelligence"
        return self.digest_service.format_daily_digest(digests, title=title)

    @staticmethod
    def save_report(report: str, output_path: str | Path) -> Path:
        """Save a report, defaulting relative paths into the reports directory."""
        path = Path(output_path)
        if not path.is_absolute() and (not path.parts or path.parts[0] != "reports"):
            path = Path("reports") / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        return path

    @staticmethod
    def _normalize_keywords(keywords: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            value = " ".join(keyword.split())
            key = value.lower()
            if value and key not in seen:
                normalized.append(value)
                seen.add(key)
        return normalized

    @staticmethod
    def _normalize_sources(sources: list[str] | None) -> list[str]:
        if not sources:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for source in sources:
            value = source.strip().lower()
            if value and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized

    @staticmethod
    def _normalize_url(url: str | None) -> str:
        if not url:
            return ""
        return url.strip().rstrip("/").lower()

    @staticmethod
    def _normalize_external_id(external_id: str | None) -> str:
        if not external_id:
            return ""
        return external_id.strip().lower()


__all__ = [
    "CollectorProtocol",
    "DailyIntelligencePipeline",
    "DailyPipelineOptions",
    "DailyPipelineResult",
    "DigestServiceProtocol",
]
