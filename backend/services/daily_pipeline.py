from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

from backend.collectors.base import ResearchItem
from backend.collectors.errors import concise_error_message, should_retry_collector_error
from backend.services.digest_service import DigestItem
from backend.services.item_fingerprint import normalize_canonical_url
from backend.services.ranking_service import RankedItem, RelevanceRankingService
from backend.services.seen_item_store import SeenItemStore
from backend.services.source_registry import SourceRegistry, SourceRegistryUpdateSummary
from backend.services.topic_registry import HotspotDiscoveryService, HotspotDiscoverySummary


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
class DeduplicationSummary:
    """Reportable deduplication counters for a pipeline run."""

    collected_items: int
    duplicates_skipped: int
    new_items_included: int


@dataclass(frozen=True)
class DailyPipelineResult:
    """Structured result for the manual daily intelligence run."""

    collected_items: list[ResearchItem]
    collector_errors: dict[str, str]
    unique_items: list[ResearchItem]
    included_items: list[ResearchItem]
    ranked_items: list[RankedItem]
    digests: list[DigestItem]
    report: str
    deduplication_summary: DeduplicationSummary
    source_registry_summary: SourceRegistryUpdateSummary | None = None
    hotspot_discovery_summary: HotspotDiscoverySummary | None = None
    output_path: Path | None = None


@dataclass(frozen=True)
class DailyPipelineOptions:
    """Manual daily pipeline input options."""

    keywords: list[str]
    user_profile: str | None = None
    max_items: int = 10
    sources: list[str] = field(default_factory=list)
    output_path: str | Path | None = None
    max_failed_source_retries: int = 5
    failed_source_retry_delay_seconds: float = 2.0
    include_seen_items: bool = False
    update_source_registry: bool = False
    update_hotspots: bool = False


@dataclass(frozen=True)
class CollectorRunResult:
    """Items and final source errors from collector execution."""

    items: list[ResearchItem]
    collector_errors: dict[str, str]


class DailyIntelligencePipeline:
    """Manual collect-rank-digest pipeline with no scheduler or database dependency."""

    def __init__(
        self,
        collectors: dict[str, CollectorProtocol],
        digest_service: DigestServiceProtocol,
        ranking_service: RelevanceRankingService | None = None,
        candidate_pool_multiplier: int = 5,
        max_failed_source_retries: int = 5,
        failed_source_retry_delay_seconds: float = 2.0,
        seen_item_store: SeenItemStore | None = None,
        source_registry: SourceRegistry | None = None,
        hotspot_discovery_service: HotspotDiscoveryService | None = None,
    ) -> None:
        self.collectors = {name.strip().lower(): collector for name, collector in collectors.items()}
        self.digest_service = digest_service
        self.ranking_service = ranking_service or RelevanceRankingService()
        self.candidate_pool_multiplier = max(1, candidate_pool_multiplier)
        self.max_failed_source_retries = max(0, max_failed_source_retries)
        self.failed_source_retry_delay_seconds = max(0.0, failed_source_retry_delay_seconds)
        self.seen_item_store = seen_item_store
        self.source_registry = source_registry
        self.hotspot_discovery_service = hotspot_discovery_service

    async def run(
        self,
        keywords: list[str],
        user_profile: str | None = None,
        max_items: int = 10,
        sources: list[str] | None = None,
        output_path: str | Path | None = None,
        include_seen_items: bool = False,
        update_source_registry: bool = False,
        update_hotspots: bool = False,
    ) -> DailyPipelineResult:
        """Collect, deduplicate, rank, digest, format, and optionally save a daily report."""
        options = DailyPipelineOptions(
            keywords=self._normalize_keywords(keywords),
            user_profile=user_profile,
            max_items=max_items,
            sources=self._normalize_sources(sources),
            output_path=output_path,
            max_failed_source_retries=self.max_failed_source_retries,
            failed_source_retry_delay_seconds=self.failed_source_retry_delay_seconds,
            include_seen_items=include_seen_items,
            update_source_registry=update_source_registry,
            update_hotspots=update_hotspots,
        )
        if not options.keywords:
            raise ValueError("At least one keyword is required.")
        if options.max_items <= 0:
            raise ValueError("max_items must be greater than zero.")

        selected_sources = options.sources or list(self.collectors.keys())
        query = " ".join(options.keywords)
        collection_limit = options.max_items * self.candidate_pool_multiplier
        collection_result = await self._collect_items(query, collection_limit, selected_sources, options)
        collected_items = collection_result.items
        collector_errors = collection_result.collector_errors
        source_registry_summary = self._update_source_registry(collected_items, options.update_source_registry)
        hotspot_discovery_summary = self._update_hotspots(collected_items, options.update_hotspots)
        if not collected_items and len(collector_errors) == len(selected_sources):
            failed_sources = ", ".join(sorted(collector_errors))
            raise RuntimeError(f"All selected collectors failed: {failed_sources}")

        deduplicated_items = self.deduplicate_items(collected_items)
        unique_items = self._filter_seen_items(deduplicated_items, include_seen_items=options.include_seen_items)
        if not unique_items:
            deduplication_summary = DeduplicationSummary(
                collected_items=len(collected_items),
                duplicates_skipped=len(collected_items),
                new_items_included=0,
            )
            report = self.format_report(
                options.keywords,
                [],
                collector_errors,
                deduplication_summary=deduplication_summary,
                source_registry_summary=source_registry_summary,
                hotspot_discovery_summary=hotspot_discovery_summary,
                no_new_items=True,
            )
            saved_path = self.save_report(report, options.output_path) if options.output_path else None
            return DailyPipelineResult(
                collected_items=collected_items,
                collector_errors=collector_errors,
                unique_items=unique_items,
                included_items=[],
                ranked_items=[],
                digests=[],
                report=report,
                deduplication_summary=deduplication_summary,
                source_registry_summary=source_registry_summary,
                hotspot_discovery_summary=hotspot_discovery_summary,
                output_path=saved_path,
            )

        ranked_items = self.ranking_service.rank_items(
            unique_items,
            user_profile=options.user_profile,
            keywords=options.keywords,
            max_items=options.max_items,
        )
        included_items = [ranked.item for ranked in ranked_items]
        digests = await self.digest_service.summarize_items(
            included_items,
            user_profile=options.user_profile,
            max_items=options.max_items,
        )
        deduplication_summary = DeduplicationSummary(
            collected_items=len(collected_items),
            duplicates_skipped=len(collected_items) - len(unique_items),
            new_items_included=len(included_items),
        )
        report = self.format_report(
            options.keywords,
            digests,
            collector_errors,
            deduplication_summary=deduplication_summary,
            source_registry_summary=source_registry_summary,
            hotspot_discovery_summary=hotspot_discovery_summary,
        )
        saved_path = self.save_report(report, options.output_path) if options.output_path else None

        return DailyPipelineResult(
            collected_items=collected_items,
            collector_errors=collector_errors,
            unique_items=unique_items,
            included_items=included_items,
            ranked_items=ranked_items,
            digests=digests,
            report=report,
            deduplication_summary=deduplication_summary,
            source_registry_summary=source_registry_summary,
            hotspot_discovery_summary=hotspot_discovery_summary,
            output_path=saved_path,
        )

    async def _collect_items(
        self,
        query: str,
        max_items: int,
        sources: list[str],
        options: DailyPipelineOptions,
    ) -> CollectorRunResult:
        collected_items: list[ResearchItem] = []
        failed_collectors: dict[str, tuple[str, bool]] = {}
        for source in sources:
            collector = self.collectors.get(source)
            if collector is None:
                raise ValueError(f"Unknown collector source: {source}")
            try:
                collected_items.extend(await collector.collect(query=query, max_results=max_items))
            except Exception as exc:  # noqa: BLE001 - isolate collector failures for retry.
                failed_collectors[source] = (self._error_message(exc), should_retry_collector_error(exc))

        final_errors = await self._retry_failed_collectors(
            failed_collectors,
            query,
            max_items,
            options,
            collected_items,
        )
        return CollectorRunResult(items=collected_items, collector_errors=final_errors)

    async def _retry_failed_collectors(
        self,
        failed_collectors: dict[str, tuple[str, bool]],
        query: str,
        max_items: int,
        options: DailyPipelineOptions,
        collected_items: list[ResearchItem],
    ) -> dict[str, str]:
        final_errors: dict[str, str] = {}
        for source, (initial_error, retryable) in failed_collectors.items():
            collector = self.collectors[source]
            last_error = initial_error
            if not retryable:
                final_errors[source] = last_error
                continue
            succeeded = False
            for attempt in range(1, options.max_failed_source_retries + 1):
                await self._sleep_before_retry(attempt, options.failed_source_retry_delay_seconds)
                try:
                    collected_items.extend(await collector.collect(query=query, max_results=max_items))
                    succeeded = True
                    break
                except Exception as exc:  # noqa: BLE001 - retry collector failures independently.
                    last_error = self._error_message(exc)
                    if not should_retry_collector_error(exc):
                        break
            if not succeeded:
                final_errors[source] = last_error
        return final_errors

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

    def format_report(
        self,
        keywords: list[str],
        digests: list[DigestItem],
        collector_errors: dict[str, str] | None = None,
        deduplication_summary: DeduplicationSummary | None = None,
        source_registry_summary: SourceRegistryUpdateSummary | None = None,
        hotspot_discovery_summary: HotspotDiscoverySummary | None = None,
        no_new_items: bool = False,
    ) -> str:
        """Format the final markdown daily report through the digest service."""
        topic = ", ".join(keywords)
        title = f"Daily Research Intelligence - {topic}" if topic else "Daily Research Intelligence"
        sections = [self.digest_service.format_daily_digest(digests, title=title)]

        if no_new_items:
            sections.append("\n".join(["", "No new items after deduplication."]))

        if deduplication_summary is not None:
            sections.append(self._format_deduplication_summary(deduplication_summary))

        if source_registry_summary is not None:
            sections.append(self._format_source_registry_summary(source_registry_summary))

        if hotspot_discovery_summary is not None:
            sections.append(self._format_hotspot_discovery_summary(hotspot_discovery_summary))

        if not collector_errors:
            return "\n".join(sections)

        warning_lines = ["", "## Collector warnings"]
        for source, error in sorted(collector_errors.items()):
            warning_lines.append(f"- {source}: {error}")
        sections.append("\n".join(warning_lines))
        return "\n".join(sections)

    def _filter_seen_items(self, items: list[ResearchItem], include_seen_items: bool) -> list[ResearchItem]:
        if include_seen_items or self.seen_item_store is None:
            return items
        return self.seen_item_store.filter_new_items(items)

    def _update_source_registry(
        self,
        items: list[ResearchItem],
        update_source_registry: bool,
    ) -> SourceRegistryUpdateSummary | None:
        if not update_source_registry:
            return None
        if self.source_registry is None:
            return SourceRegistryUpdateSummary()
        return self.source_registry.import_from_web_results(items)

    def _update_hotspots(
        self,
        items: list[ResearchItem],
        update_hotspots: bool,
    ) -> HotspotDiscoverySummary | None:
        if not update_hotspots:
            return None
        if self.hotspot_discovery_service is None:
            return HotspotDiscoverySummary()
        return self.hotspot_discovery_service.update_registry(items)

    @staticmethod
    def _format_deduplication_summary(summary: DeduplicationSummary) -> str:
        return "\n".join(
            [
                "",
                "## Deduplication summary",
                f"- Collected items: {summary.collected_items}",
                f"- Duplicates skipped: {summary.duplicates_skipped}",
                f"- New items included: {summary.new_items_included}",
            ]
        )

    @staticmethod
    def _format_source_registry_summary(summary: SourceRegistryUpdateSummary) -> str:
        return "\n".join(
            [
                "",
                "## Source registry updates",
                f"- New sources added: {summary.new_sources_added}",
                f"- Existing sources updated: {summary.existing_sources_updated}",
                f"- Blocked domains skipped: {summary.blocked_domains_skipped}",
            ]
        )

    @staticmethod
    def _format_hotspot_discovery_summary(summary: HotspotDiscoverySummary) -> str:
        return "\n".join(
            [
                "",
                "## Hotspot discovery updates",
                f"- Candidates considered: {summary.candidates_considered}",
                f"- New topics added: {summary.new_topics_added}",
                f"- Existing topics updated: {summary.existing_topics_updated}",
            ]
        )

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
        return normalize_canonical_url(url)

    @staticmethod
    def _normalize_external_id(external_id: str | None) -> str:
        if not external_id:
            return ""
        return external_id.strip().lower()

    @staticmethod
    async def _sleep_before_retry(attempt: int, base_delay_seconds: float) -> None:
        if base_delay_seconds <= 0:
            return
        delay = base_delay_seconds * min(2 ** (attempt - 1), 8)
        await asyncio.sleep(delay)

    @staticmethod
    def _error_message(exc: Exception) -> str:
        return concise_error_message(exc)


__all__ = [
    "CollectorProtocol",
    "CollectorRunResult",
    "DailyIntelligencePipeline",
    "DailyPipelineOptions",
    "DailyPipelineResult",
    "DeduplicationSummary",
    "DigestServiceProtocol",
]
