from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.collectors.base import ResearchItem


logger = logging.getLogger(__name__)


TopicLanguage = Literal["en", "zh", "mixed"]


SEED_TOPIC_DEFINITIONS: list[tuple[str, list[str]]] = [
    ("AI for biology", ["AI biology", "AI4Bio", "artificial intelligence for biology"]),
    ("bioinformatics foundation model", ["bioinformatics large model", "bioinformatics FM"]),
    ("single-cell foundation model", ["single cell foundation model", "single-cell FM"]),
    ("perturbation prediction", ["cell perturbation prediction", "perturbation response prediction"]),
    ("drug response", ["drug response prediction", "therapy response"]),
    ("virtual cell", ["AI virtual cell", "virtual cell model"]),
    ("spatial transcriptomics", ["spatial omics", "spatial transcriptome"]),
    ("生信 大模型", ["生信大模型", "生物信息 大模型"]),
    ("单细胞 基础模型", ["单细胞基础模型", "单细胞大模型"]),
    ("扰动预测", ["细胞扰动预测", "扰动响应预测"]),
    ("药物反应", ["药物响应", "药物反应预测"]),
    ("空间转录组", ["空间组学", "空间转录组学"]),
]

AI_TERMS = {
    "ai",
    "artificial",
    "foundation",
    "model",
    "models",
    "learning",
    "prediction",
    "predictive",
    "transformer",
    "llm",
    "virtual",
    "benchmark",
}

BIO_TERMS = {
    "biology",
    "bioinformatics",
    "biomedical",
    "single",
    "cell",
    "spatial",
    "transcriptomics",
    "transcriptome",
    "genomics",
    "proteomics",
    "protein",
    "drug",
    "response",
    "perturbation",
    "omics",
}

ZH_HOTSPOT_TERMS = ("生信", "大模型", "单细胞", "基础模型", "扰动", "预测", "药物", "反应", "空间", "转录组")


class TopicRecord(BaseModel):
    """Persisted AI + bioinformatics hotspot topic."""

    topic: str
    language: TopicLanguage
    aliases: list[str] = Field(default_factory=list)
    score: float = 0.0
    first_seen_at: datetime
    last_seen_at: datetime
    source_count: int = 0
    item_count: int = 0
    enabled: bool = True


@dataclass(frozen=True)
class TopicRegistryChange:
    """Result of adding or updating a topic."""

    status: str
    record: TopicRecord | None = None


@dataclass(frozen=True)
class HotspotCandidate:
    """Candidate topic aggregated from collected research items."""

    topic: str
    language: TopicLanguage
    aliases: list[str]
    score: float
    source_count: int
    item_count: int


@dataclass(frozen=True)
class HotspotDiscoverySummary:
    """Counters from updating the topic registry."""

    candidates_considered: int = 0
    new_topics_added: int = 0
    existing_topics_updated: int = 0


class TopicRegistry:
    """Lightweight JSON-backed topic registry for AI + bioinformatics hotspots."""

    def __init__(self, path: str | Path = "data/topic_registry.json", include_seed_topics: bool = True) -> None:
        self.path = Path(path)
        self.include_seed_topics = include_seed_topics

    def load(self) -> list[TopicRecord]:
        """Load registry topics, merging built-in bilingual seed topics."""
        records = self._read_records()
        if self.include_seed_topics:
            records = self._merge_seed_records(records)
        return self._sorted_records(records)

    def save(self, records: list[TopicRecord]) -> None:
        """Persist topic records to JSON."""
        self._write_records(self._sorted_records(records))

    def add_or_update(self, record: TopicRecord) -> TopicRegistryChange:
        """Add a topic or update an existing topic/alias."""
        prepared = self._prepare_record(record)
        records = self.load()
        existing_index = self._find_existing_index(records, prepared)
        if existing_index is None:
            records.append(prepared)
            self.save(records)
            return TopicRegistryChange(status="added", record=prepared)

        merged = self._merge_records(records[existing_index], prepared)
        records[existing_index] = merged
        self.save(records)
        return TopicRegistryChange(status="updated", record=merged)

    def list_enabled(
        self,
        min_score: float = 0.0,
        limit: int | None = None,
    ) -> list[TopicRecord]:
        """Return enabled topics above a score threshold."""
        records = [record for record in self.load() if record.enabled and record.score >= min_score]
        if limit is not None:
            return records[: max(0, limit)]
        return records

    def disable(self, topic_or_alias: str) -> bool:
        """Disable a topic by exact topic text or alias."""
        key = topic_key(topic_or_alias)
        if not key:
            return False
        records = self.load()
        changed = False
        for index, record in enumerate(records):
            keys = {topic_key(record.topic), *(topic_key(alias) for alias in record.aliases)}
            if key in keys:
                records[index] = record.model_copy(update={"enabled": False})
                changed = True
                break
        if changed:
            self.save(records)
        return changed

    def build_record(
        self,
        topic: str,
        aliases: list[str] | None = None,
        score: float = 0.5,
        enabled: bool = True,
        source_count: int = 0,
        item_count: int = 0,
    ) -> TopicRecord:
        """Build a normalized TopicRecord."""
        normalized_topic = normalize_topic(topic)
        if not normalized_topic:
            raise ValueError("topic must not be empty")
        now = utc_now()
        return TopicRecord(
            topic=normalized_topic,
            language=detect_language(normalized_topic),
            aliases=normalize_aliases(aliases or [], normalized_topic),
            score=clamp_score(score),
            first_seen_at=now,
            last_seen_at=now,
            source_count=max(0, int(source_count)),
            item_count=max(0, int(item_count)),
            enabled=enabled,
        )

    def export_document(self) -> dict[str, Any]:
        """Return the full JSON-serializable registry document."""
        return {"topics": [record.model_dump(mode="json") for record in self.load()]}

    def _read_records(self) -> list[TopicRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed topic registry JSON", extra={"path": str(self.path)})
            return []

        raw_records = data.get("topics", []) if isinstance(data, dict) else data
        if not isinstance(raw_records, list):
            return []

        records: list[TopicRecord] = []
        for index, raw_record in enumerate(raw_records):
            if not isinstance(raw_record, dict):
                continue
            try:
                records.append(TopicRecord.model_validate(raw_record))
            except ValidationError:
                logger.warning(
                    "Skipping invalid topic registry record",
                    extra={"path": str(self.path), "record_index": index},
                )
        return records

    def _write_records(self, records: list[TopicRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"topics": [record.model_dump(mode="json") for record in records]}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    def _merge_seed_records(self, records: list[TopicRecord]) -> list[TopicRecord]:
        merged = list(records)
        for seed in seed_topic_records():
            index = self._find_existing_index(merged, seed)
            if index is None:
                merged.append(seed)
            else:
                merged[index] = self._merge_records(merged[index], seed, preserve_existing_score=True)
        return merged

    def _prepare_record(self, record: TopicRecord) -> TopicRecord:
        normalized_topic = normalize_topic(record.topic)
        if not normalized_topic:
            raise ValueError("topic must not be empty")
        now = utc_now()
        return record.model_copy(
            update={
                "topic": normalized_topic,
                "language": detect_language(normalized_topic),
                "aliases": normalize_aliases(record.aliases, normalized_topic),
                "score": clamp_score(record.score),
                "first_seen_at": record.first_seen_at or now,
                "last_seen_at": record.last_seen_at or now,
                "source_count": max(0, int(record.source_count)),
                "item_count": max(0, int(record.item_count)),
            }
        )

    @staticmethod
    def _find_existing_index(records: list[TopicRecord], incoming: TopicRecord) -> int | None:
        incoming_keys = {topic_key(incoming.topic), *(topic_key(alias) for alias in incoming.aliases)}
        for index, record in enumerate(records):
            record_keys = {topic_key(record.topic), *(topic_key(alias) for alias in record.aliases)}
            if incoming_keys & record_keys:
                return index
        return None

    @staticmethod
    def _merge_records(
        existing: TopicRecord,
        incoming: TopicRecord,
        preserve_existing_score: bool = False,
    ) -> TopicRecord:
        score = existing.score if preserve_existing_score else clamp_score(existing.score + incoming.score)
        return existing.model_copy(
            update={
                "aliases": normalize_aliases([*existing.aliases, incoming.topic, *incoming.aliases], existing.topic),
                "score": score,
                "last_seen_at": max(existing.last_seen_at, incoming.last_seen_at),
                "source_count": max(existing.source_count, incoming.source_count),
                "item_count": existing.item_count + incoming.item_count,
                "enabled": existing.enabled and incoming.enabled,
            }
        )

    @staticmethod
    def _sorted_records(records: list[TopicRecord]) -> list[TopicRecord]:
        return sorted(records, key=lambda record: (-record.score, record.topic.casefold()))


class HotspotDiscoveryService:
    """Rule-based MVP hotspot discovery for AI + bioinformatics items."""

    def __init__(
        self,
        topic_registry: TopicRegistry | None = None,
        max_topics: int = 50,
        min_score: float = 0.2,
    ) -> None:
        self.topic_registry = topic_registry or TopicRegistry()
        self.max_topics = max(1, max_topics)
        self.min_score = max(0.0, min_score)

    def extract_candidates(self, items: list[ResearchItem]) -> list[HotspotCandidate]:
        """Extract candidate hotspot topics from collected research items."""
        aggregates: dict[str, _TopicAggregate] = {}
        seed_records = seed_topic_records()
        for item in items:
            text = item_text(item)
            source_name = item.source_name.strip() or "unknown"
            topics = self._topics_from_text(text, seed_records)
            for topic in topics:
                key = topic_key(topic)
                if not key:
                    continue
                aggregate = aggregates.setdefault(key, _TopicAggregate(topic=normalize_topic(topic)))
                aggregate.item_count += 1
                aggregate.sources.add(source_name)

        candidates = [aggregate.to_candidate() for aggregate in aggregates.values()]
        return [
            candidate
            for candidate in sorted(candidates, key=lambda value: (-value.score, value.topic.casefold()))[: self.max_topics]
            if candidate.score >= self.min_score
        ]

    def update_registry(self, items: list[ResearchItem]) -> HotspotDiscoverySummary:
        """Extract hotspots from items and persist them to the topic registry."""
        candidates = self.extract_candidates(items)
        added = 0
        updated = 0
        for candidate in candidates:
            change = self.topic_registry.add_or_update(
                self.topic_registry.build_record(
                    topic=candidate.topic,
                    aliases=candidate.aliases,
                    score=candidate.score,
                    source_count=candidate.source_count,
                    item_count=candidate.item_count,
                )
            )
            if change.status == "added":
                added += 1
            elif change.status == "updated":
                updated += 1
        return HotspotDiscoverySummary(
            candidates_considered=len(candidates),
            new_topics_added=added,
            existing_topics_updated=updated,
        )

    def _topics_from_text(self, text: str, seed_records: list[TopicRecord]) -> set[str]:
        topics: set[str] = set()
        for seed in seed_records:
            if any(contains_topic(text, phrase) for phrase in [seed.topic, *seed.aliases]):
                topics.add(seed.topic)

        topics.update(extract_english_hotspot_phrases(text))
        topics.update(extract_chinese_hotspot_phrases(text))
        return {topic for topic in topics if is_ai_bio_topic(topic)}


@dataclass
class _TopicAggregate:
    topic: str
    item_count: int = 0
    sources: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.sources is None:
            self.sources = set()

    def to_candidate(self) -> HotspotCandidate:
        source_count = len(self.sources)
        score = clamp_score(0.2 * self.item_count + 0.05 * source_count)
        return HotspotCandidate(
            topic=self.topic,
            language=detect_language(self.topic),
            aliases=[],
            score=score,
            source_count=source_count,
            item_count=self.item_count,
        )


def seed_topic_records() -> list[TopicRecord]:
    now = utc_now()
    return [
        TopicRecord(
            topic=topic,
            language=detect_language(topic),
            aliases=normalize_aliases(aliases, topic),
            score=0.6,
            first_seen_at=now,
            last_seen_at=now,
            source_count=0,
            item_count=0,
            enabled=True,
        )
        for topic, aliases in SEED_TOPIC_DEFINITIONS
    ]


def item_text(item: ResearchItem) -> str:
    metadata_parts: list[str] = []
    for key in ("snippet", "search_query", "search_category", "tags", "keywords", "source_type", "item_type"):
        value = item.metadata.get(key)
        if isinstance(value, list):
            metadata_parts.extend(str(part) for part in value)
        elif value is not None:
            metadata_parts.append(str(value))
    return " ".join(
        [
            item.title,
            item.abstract or "",
            item.raw_text or "",
            " ".join(item.keywords),
            " ".join(metadata_parts),
        ]
    )


def extract_english_hotspot_phrases(text: str) -> set[str]:
    normalized = re.sub(r"[^a-zA-Z0-9+\- ]+", " ", text.casefold())
    phrases: set[str] = set()
    fixed_patterns = [
        (r"\bai for biology\b|\bai4bio\b|\bartificial intelligence for biology\b", "AI for biology"),
        (r"\bbioinformatics foundation models?\b", "bioinformatics foundation model"),
        (r"\bsingle[- ]cell foundation models?\b", "single-cell foundation model"),
        (r"\bperturbation (?:response )?prediction\b", "perturbation prediction"),
        (r"\bdrug response(?: prediction)?\b", "drug response"),
        (r"\bvirtual cell(?: model)?\b", "virtual cell"),
        (r"\bspatial transcriptomics?\b|\bspatial transcriptome\b", "spatial transcriptomics"),
    ]
    for pattern, topic in fixed_patterns:
        if re.search(pattern, normalized):
            phrases.add(topic)

    foundation_matches = re.finditer(
        r"\b([a-z0-9+\-]+(?: [a-z0-9+\-]+){0,2}) foundation models?\b",
        normalized,
    )
    for match in foundation_matches:
        prefix = match.group(1)
        prefix_tokens = set(prefix.split())
        if prefix_tokens & BIO_TERMS:
            phrases.add(canonical_english_topic(f"{prefix} foundation model"))

    return {phrase for phrase in phrases if is_ai_bio_topic(phrase)}


def extract_chinese_hotspot_phrases(text: str) -> set[str]:
    chunks = re.findall(r"[\u4e00-\u9fffA-Za-z0-9 ]{2,24}", text)
    phrases: set[str] = set()
    for chunk in chunks:
        normalized = re.sub(r"\s+", " ", chunk).strip()
        compact = normalized.replace(" ", "")
        if any(term in compact for term in ZH_HOTSPOT_TERMS):
            for seed_topic, _aliases in SEED_TOPIC_DEFINITIONS:
                if has_cjk(seed_topic) and contains_topic(compact, seed_topic):
                    phrases.add(seed_topic)
            if has_cjk(normalized) and len(compact) <= 16:
                phrases.add(normalized)
    return phrases


def is_ai_bio_topic(topic: str) -> bool:
    if is_seed_topic(topic):
        return True
    normalized = topic.casefold()
    if has_cjk(normalized):
        return any(term in normalized.replace(" ", "") for term in ZH_HOTSPOT_TERMS)
    tokens = set(re.findall(r"[a-zA-Z][a-zA-Z0-9+\-]*", normalized))
    return bool(tokens & AI_TERMS and tokens & BIO_TERMS)


def is_seed_topic(topic: str) -> bool:
    candidate = topic_key(topic)
    for seed_topic, aliases in SEED_TOPIC_DEFINITIONS:
        seed_keys = {topic_key(seed_topic), *(topic_key(alias) for alias in aliases)}
        if candidate in seed_keys:
            return True
    return False


def contains_topic(text: str, phrase: str) -> bool:
    if has_cjk(phrase):
        return normalize_cjk_text(phrase) in normalize_cjk_text(text)
    return normalize_topic(phrase).casefold() in re.sub(r"\s+", " ", text.casefold())


def normalize_topic(value: str) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""
    if not has_cjk(text):
        text = canonical_english_topic(text)
    return text


def canonical_english_topic(value: str) -> str:
    text = " ".join(value.replace("_", " ").split())
    text = re.sub(r"\bsingle cell\b", "single-cell", text, flags=re.IGNORECASE)
    text = re.sub(r"\blarge language model\b", "LLM", text, flags=re.IGNORECASE)
    return text


def normalize_aliases(aliases: list[str], topic: str) -> list[str]:
    topic_key_value = topic_key(topic)
    normalized: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        value = normalize_topic(alias)
        key = topic_key(value)
        if value and key != topic_key_value and key not in seen:
            normalized.append(value)
            seen.add(key)
    return normalized


def topic_key(value: str) -> str:
    normalized = normalize_topic(value)
    if has_cjk(normalized):
        return normalize_cjk_text(normalized)
    return normalized.casefold()


def detect_language(value: str) -> TopicLanguage:
    has_chinese = has_cjk(value)
    has_latin = bool(re.search(r"[A-Za-z]", value))
    if has_chinese and has_latin:
        return "mixed"
    if has_chinese:
        return "zh"
    return "en"


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def normalize_cjk_text(value: str) -> str:
    return re.sub(r"\s+", "", value.casefold())


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "HotspotCandidate",
    "HotspotDiscoveryService",
    "HotspotDiscoverySummary",
    "SEED_TOPIC_DEFINITIONS",
    "TopicRecord",
    "TopicRegistry",
    "TopicRegistryChange",
    "detect_language",
    "extract_chinese_hotspot_phrases",
    "extract_english_hotspot_phrases",
    "seed_topic_records",
    "topic_key",
]
