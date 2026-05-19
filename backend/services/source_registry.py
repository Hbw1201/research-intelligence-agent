from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError

from backend.collectors.base import ResearchItem
from backend.services.item_fingerprint import normalize_canonical_url


logger = logging.getLogger(__name__)


SourceType = Literal[
    "rss",
    "website",
    "github",
    "pubmed",
    "arxiv",
    "dataset",
    "lab_page",
    "company_research",
    "news",
    "blog",
    "other",
]

SOURCE_TYPES: set[str] = {
    "rss",
    "website",
    "github",
    "pubmed",
    "arxiv",
    "dataset",
    "lab_page",
    "company_research",
    "news",
    "blog",
    "other",
}

REGISTRY_CANDIDATE_ITEM_TYPES = {
    "news",
    "blog",
    "dataset",
    "benchmark",
    "lab_page",
    "company_research",
}

REGISTRY_CANDIDATE_SOURCE_TYPES = {
    "news",
    "blog",
    "dataset",
    "benchmark",
    "lab_page",
    "company_research",
}

DOMAIN_DEDUP_SOURCE_TYPES = {
    "website",
    "dataset",
    "lab_page",
    "company_research",
    "news",
    "blog",
    "other",
}


class SourceRecord(BaseModel):
    """Persisted source candidate for reuse by future collection runs."""

    source_id: str
    name: str
    url: str
    source_type: SourceType
    domain: str
    tags: list[str] = Field(default_factory=list)
    priority: float = 1.0
    enabled: bool = True
    discovered_from: str | None = None
    first_seen_at: datetime
    last_seen_at: datetime
    last_checked_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class SourceRegistryUpdateSummary:
    """Counters for reporting source-registry updates."""

    new_sources_added: int = 0
    existing_sources_updated: int = 0
    blocked_domains_skipped: int = 0
    candidates_considered: int = 0

    @property
    def total_changed(self) -> int:
        return self.new_sources_added + self.existing_sources_updated


@dataclass(frozen=True)
class SourceRegistryChange:
    """Result of one registry write attempt."""

    status: str
    record: SourceRecord | None = None


class SourceRegistry:
    """Lightweight JSON-backed registry of trusted or blocked sources."""

    def __init__(self, path: str | Path = "data/source_registry.json") -> None:
        self.path = Path(path)

    def load(self) -> list[SourceRecord]:
        """Load source records from the JSON registry file."""
        records, _blocked_domains = self._read_document()
        return records

    def save(self, records: list[SourceRecord]) -> None:
        """Persist source records while preserving blocked domains."""
        _existing_records, blocked_domains = self._read_document()
        self._write_document(records, blocked_domains)

    def add_or_update(self, record: SourceRecord) -> SourceRegistryChange:
        """Add a source or update an existing source by normalized URL/domain."""
        prepared = self._prepare_record(record)
        records, blocked_domains = self._read_document()
        if self._domain_is_blocked(prepared.domain, blocked_domains):
            return SourceRegistryChange(status="blocked")

        existing_index = self._find_existing_index(records, prepared)
        if existing_index is None:
            records.append(prepared)
            self._write_document(records, blocked_domains)
            return SourceRegistryChange(status="added", record=prepared)

        merged = self._merge_records(records[existing_index], prepared)
        records[existing_index] = merged
        self._write_document(records, blocked_domains)
        return SourceRegistryChange(status="updated", record=merged)

    def list_enabled(self, source_type: str | None = None) -> list[SourceRecord]:
        """Return enabled records, optionally filtered by source_type."""
        normalized_type = self._normalize_source_type_filter(source_type)
        records = [record for record in self.load() if record.enabled]
        if normalized_type is None:
            return records
        return [record for record in records if record.source_type == normalized_type]

    def disable(self, source_id_or_url: str) -> bool:
        """Disable a record matched by source_id, URL, or domain."""
        key = source_id_or_url.strip()
        if not key:
            return False
        url_key = normalize_canonical_url(key)
        domain_key = normalize_domain(key)
        records, blocked_domains = self._read_document()
        changed = False
        for index, record in enumerate(records):
            if (
                record.source_id == key
                or normalize_canonical_url(record.url) == url_key
                or normalize_domain(record.url) == domain_key
                or record.domain == domain_key
            ):
                records[index] = record.model_copy(update={"enabled": False})
                changed = True
                break
        if changed:
            self._write_document(records, blocked_domains)
        return changed

    def block_domain(self, domain: str) -> bool:
        """Add a domain to the block list and disable matching existing sources."""
        normalized = normalize_domain(domain)
        if not normalized:
            raise ValueError("domain must not be empty")

        records, blocked_domains = self._read_document()
        was_new = normalized not in blocked_domains
        blocked_domains.add(normalized)
        updated_records = [
            record.model_copy(update={"enabled": False}) if self._domain_is_blocked(record.domain, {normalized}) else record
            for record in records
        ]
        self._write_document(updated_records, blocked_domains)
        return was_new

    def is_domain_blocked(self, domain: str) -> bool:
        """Return whether a domain or its parent domain is blocked."""
        _records, blocked_domains = self._read_document()
        return self._domain_is_blocked(normalize_domain(domain), blocked_domains)

    def import_from_web_results(self, items: list[ResearchItem]) -> SourceRegistryUpdateSummary:
        """Register useful web-discovery sources and discovered RSS feeds."""
        summary = _MutableSourceRegistryUpdateSummary()
        for item in items:
            for record in self._records_from_item(item):
                summary.candidates_considered += 1
                change = self.add_or_update(record)
                if change.status == "added":
                    summary.new_sources_added += 1
                elif change.status == "updated":
                    summary.existing_sources_updated += 1
                elif change.status == "blocked":
                    summary.blocked_domains_skipped += 1
        return summary.freeze()

    def export_document(self) -> dict[str, Any]:
        """Return the full registry document for CLI export."""
        records, blocked_domains = self._read_document()
        return self._document(records, blocked_domains)

    def build_record(
        self,
        *,
        name: str,
        url: str,
        source_type: str,
        tags: list[str] | None = None,
        priority: float = 1.0,
        enabled: bool = True,
        discovered_from: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SourceRecord:
        """Build a normalized SourceRecord for callers that do not have IDs yet."""
        normalized_url = normalize_source_url(url)
        domain = normalize_domain(normalized_url)
        if not normalized_url or not domain:
            raise ValueError("url must include a valid domain")
        normalized_source_type = normalize_source_type(source_type)
        now = utc_now()
        return SourceRecord(
            source_id=source_id_for_url(normalized_url),
            name=clean_name(name) or domain,
            url=normalized_url,
            source_type=normalized_source_type,
            domain=domain,
            tags=normalize_tags(tags or []),
            priority=float(priority),
            enabled=enabled,
            discovered_from=clean_optional(discovered_from),
            first_seen_at=now,
            last_seen_at=now,
            metadata=metadata or {},
        )

    def _records_from_item(self, item: ResearchItem) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        if self._is_registry_candidate(item):
            records.append(self._record_from_item(item))
        records.extend(self._rss_records_from_item(item))
        return records

    def _record_from_item(self, item: ResearchItem) -> SourceRecord:
        source_type = source_type_from_item(item)
        metadata = {
            "item_type": item.item_type,
            "source_name": item.source_name,
            "source_type": item.source_type,
            "search_query": item.metadata.get("search_query"),
            "search_category": item.metadata.get("search_category"),
            "search_source": item.metadata.get("search_source"),
        }
        return self.build_record(
            name=item.title,
            url=item.url,
            source_type=source_type,
            tags=item_tags(item),
            priority=1.0,
            enabled=True,
            discovered_from=clean_optional(item.metadata.get("search_query")) or item.source_name,
            metadata={key: value for key, value in metadata.items() if value is not None},
        )

    def _rss_records_from_item(self, item: ResearchItem) -> list[SourceRecord]:
        records: list[SourceRecord] = []
        for feed_url in discovered_feed_urls(item):
            try:
                records.append(
                    self.build_record(
                        name=f"{item.title} RSS",
                        url=feed_url,
                        source_type="rss",
                        tags=normalize_tags([*item.keywords, "rss"]),
                        priority=1.0,
                        enabled=True,
                        discovered_from=item.url,
                        metadata={
                            "parent_url": item.url,
                            "parent_title": item.title,
                            "source_name": item.source_name,
                        },
                    )
                )
            except ValueError:
                logger.warning("Skipping invalid discovered RSS feed URL", extra={"feed_url": feed_url})
        return records

    @staticmethod
    def _is_registry_candidate(item: ResearchItem) -> bool:
        return item.item_type in REGISTRY_CANDIDATE_ITEM_TYPES or item.source_type in REGISTRY_CANDIDATE_SOURCE_TYPES

    def _prepare_record(self, record: SourceRecord) -> SourceRecord:
        normalized_url = normalize_source_url(record.url)
        domain = normalize_domain(normalized_url or record.domain)
        if not normalized_url or not domain:
            raise ValueError("source record must include a valid URL and domain")

        normalized_type = normalize_source_type(record.source_type)
        now = utc_now()
        first_seen_at = record.first_seen_at or now
        last_seen_at = record.last_seen_at or now
        source_id = record.source_id.strip() or source_id_for_url(normalized_url)
        return record.model_copy(
            update={
                "source_id": source_id,
                "name": clean_name(record.name) or domain,
                "url": normalized_url,
                "source_type": normalized_type,
                "domain": domain,
                "tags": normalize_tags(record.tags),
                "priority": float(record.priority),
                "first_seen_at": first_seen_at,
                "last_seen_at": last_seen_at,
                "discovered_from": clean_optional(record.discovered_from),
            }
        )

    def _find_existing_index(self, records: list[SourceRecord], record: SourceRecord) -> int | None:
        url_key = normalize_canonical_url(record.url)
        for index, existing in enumerate(records):
            if normalize_canonical_url(existing.url) == url_key:
                return index

        if record.source_type in DOMAIN_DEDUP_SOURCE_TYPES:
            for index, existing in enumerate(records):
                if existing.source_type in DOMAIN_DEDUP_SOURCE_TYPES and existing.domain == record.domain:
                    return index
        return None

    @staticmethod
    def _merge_records(existing: SourceRecord, incoming: SourceRecord) -> SourceRecord:
        metadata = dict(existing.metadata)
        metadata.update(incoming.metadata)
        return existing.model_copy(
            update={
                "name": incoming.name or existing.name,
                "url": incoming.url or existing.url,
                "source_type": incoming.source_type or existing.source_type,
                "domain": incoming.domain or existing.domain,
                "tags": normalize_tags([*existing.tags, *incoming.tags]),
                "priority": incoming.priority,
                "enabled": incoming.enabled,
                "discovered_from": incoming.discovered_from or existing.discovered_from,
                "last_seen_at": incoming.last_seen_at,
                "last_checked_at": incoming.last_checked_at or existing.last_checked_at,
                "metadata": metadata,
            }
        )

    @staticmethod
    def _normalize_source_type_filter(source_type: str | None) -> str | None:
        if source_type is None:
            return None
        return normalize_source_type(source_type)

    def _read_document(self) -> tuple[list[SourceRecord], set[str]]:
        if not self.path.exists():
            return [], set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed source registry JSON", extra={"path": str(self.path)})
            return [], set()

        if isinstance(data, list):
            raw_records = data
            raw_blocked_domains: list[Any] = []
        elif isinstance(data, dict):
            raw_records = data.get("sources", [])
            raw_blocked_domains = data.get("blocked_domains", [])
        else:
            logger.warning("Skipping unsupported source registry document", extra={"path": str(self.path)})
            return [], set()

        records: list[SourceRecord] = []
        if isinstance(raw_records, list):
            for index, raw_record in enumerate(raw_records):
                if not isinstance(raw_record, dict):
                    continue
                try:
                    records.append(SourceRecord.model_validate(raw_record))
                except ValidationError:
                    logger.warning(
                        "Skipping invalid source registry record",
                        extra={"path": str(self.path), "record_index": index},
                    )

        blocked_domains = {
            normalized
            for raw_domain in raw_blocked_domains
            if (normalized := normalize_domain(str(raw_domain)))
        }
        return records, blocked_domains

    def _write_document(self, records: list[SourceRecord], blocked_domains: set[str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._document(records, blocked_domains), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _document(records: list[SourceRecord], blocked_domains: set[str]) -> dict[str, Any]:
        return {
            "blocked_domains": sorted(blocked_domains),
            "sources": [record.model_dump(mode="json") for record in records],
        }

    @staticmethod
    def _domain_is_blocked(domain: str, blocked_domains: set[str]) -> bool:
        normalized = normalize_domain(domain)
        return any(normalized == blocked or normalized.endswith(f".{blocked}") for blocked in blocked_domains)


@dataclass
class _MutableSourceRegistryUpdateSummary:
    new_sources_added: int = 0
    existing_sources_updated: int = 0
    blocked_domains_skipped: int = 0
    candidates_considered: int = 0

    def freeze(self) -> SourceRegistryUpdateSummary:
        return SourceRegistryUpdateSummary(
            new_sources_added=self.new_sources_added,
            existing_sources_updated=self.existing_sources_updated,
            blocked_domains_skipped=self.blocked_domains_skipped,
            candidates_considered=self.candidates_considered,
        )


def source_type_from_item(item: ResearchItem) -> str:
    item_type = item.item_type.strip().lower()
    source_type = item.source_type.strip().lower()
    if item_type in {"dataset", "lab_page", "company_research", "news", "blog"}:
        return item_type
    if source_type in {"dataset", "lab_page", "company_research", "news", "blog"}:
        return source_type
    if item_type == "benchmark" or source_type == "benchmark":
        return "website"
    return "website"


def discovered_feed_urls(item: ResearchItem) -> list[str]:
    raw_value = item.metadata.get("discovered_feeds")
    if raw_value is None:
        return []
    if isinstance(raw_value, str):
        values = [raw_value]
    elif isinstance(raw_value, list):
        values = raw_value
    else:
        return []

    normalized_urls: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_source_url(str(value))
        if normalized and normalized not in seen:
            normalized_urls.append(normalized)
            seen.add(normalized)
    return normalized_urls


def item_tags(item: ResearchItem) -> list[str]:
    tags = [*item.keywords, item.item_type]
    category = item.metadata.get("search_category")
    if category:
        tags.append(str(category))
    return normalize_tags(tags)


def normalize_source_url(url: str | None) -> str:
    if not url:
        return ""
    raw_url = str(url).strip()
    if not raw_url:
        return ""
    parsed = urlsplit(raw_url)
    if not parsed.scheme and "." in raw_url.split("/", 1)[0]:
        raw_url = f"https://{raw_url}"
    return normalize_canonical_url(raw_url)


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    parsed = urlsplit(text if "://" in text else f"https://{text}")
    domain = parsed.hostname or text.split("/", 1)[0]
    return domain.lower().removeprefix("www.").strip(".")


def normalize_source_type(source_type: str) -> SourceType:
    normalized = source_type.strip().lower()
    if normalized not in SOURCE_TYPES:
        raise ValueError(f"Unsupported source_type: {source_type}")
    return normalized  # type: ignore[return-value]


def normalize_tags(tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        value = " ".join(str(tag).strip().split()).lower()
        if value and value not in seen:
            normalized_tags.append(value)
            seen.add(value)
    return normalized_tags


def clean_name(value: str | None) -> str:
    return " ".join(str(value or "").split())


def clean_optional(value: Any) -> str | None:
    cleaned = clean_name(str(value)) if value is not None else ""
    return cleaned or None


def source_id_for_url(url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return f"src_{digest}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "SOURCE_TYPES",
    "SourceRecord",
    "SourceRegistry",
    "SourceRegistryChange",
    "SourceRegistryUpdateSummary",
    "discovered_feed_urls",
    "normalize_domain",
    "normalize_source_url",
    "source_id_for_url",
    "source_type_from_item",
]
