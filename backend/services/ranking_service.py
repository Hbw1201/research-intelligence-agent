from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from backend.collectors.base import ResearchItem


DEFAULT_COMPONENT_WEIGHTS = {
    "keyword_score": 0.25,
    "profile_score": 0.20,
    "freshness_score": 0.10,
    "source_score": 0.10,
    "item_type_score": 0.10,
    "author_score": 0.15,
    "media_score": 0.10,
}

DEFAULT_SOURCE_WEIGHTS = {
    "arxiv": 0.90,
    "pubmed": 0.90,
    "github": 0.80,
    "rss": 0.60,
}

DEFAULT_ITEM_TYPE_WEIGHTS = {
    "paper": 0.90,
    "repository": 0.80,
    "news": 0.60,
    "dataset": 0.80,
    "method": 0.80,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "research",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class RankingExternalSignals:
    """Optional precomputed signals from future authority/media pipelines."""

    author_score: float | None = None
    media_score: float | None = None
    author_metrics: dict[str, Any] | None = None
    media_mentions: list[Any] | None = None


@dataclass(frozen=True)
class RankedItem:
    """Research item with deterministic ranking component scores."""

    item: ResearchItem
    final_score: float
    keyword_score: float
    freshness_score: float
    source_score: float
    item_type_score: float
    profile_score: float
    author_score: float
    media_score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RankingConfig:
    """Configurable weights for deterministic MVP ranking."""

    component_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_COMPONENT_WEIGHTS))
    source_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SOURCE_WEIGHTS))
    item_type_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ITEM_TYPE_WEIGHTS))
    default_source_score: float = 0.50
    default_item_type_score: float = 0.50
    freshness_window_days: int = 365
    recent_item_days: int = 14


class RelevanceRankingService:
    """Lightweight deterministic ranking for collected research items."""

    def __init__(
        self,
        config: RankingConfig | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config or RankingConfig()
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def score_item(
        self,
        item: ResearchItem,
        user_profile: str | None = None,
        keywords: list[str] | None = None,
        external_signals: RankingExternalSignals | None = None,
    ) -> RankedItem:
        """Score a single item without external API or database calls."""
        reasons: list[str] = []
        item_text = self._item_text(item)

        keyword_score = self._keyword_score(item_text, keywords, reasons)
        profile_score = self._profile_score(item_text, user_profile, reasons)
        freshness_score = self._freshness_score(item, reasons)
        source_score = self._weighted_lookup(item.source_name, self.config.source_weights, self.config.default_source_score)
        item_type_score = self._weighted_lookup(
            item.item_type,
            self.config.item_type_weights,
            self.config.default_item_type_score,
        )
        author_score = self._signal_score(external_signals.author_score if external_signals else None)
        media_score = self._signal_score(external_signals.media_score if external_signals else None)

        self._add_source_reasons(item, source_score, item_type_score, reasons)
        self._add_external_signal_reasons(author_score, media_score, external_signals, reasons)

        scores = {
            "keyword_score": keyword_score,
            "profile_score": profile_score,
            "freshness_score": freshness_score,
            "source_score": source_score,
            "item_type_score": item_type_score,
            "author_score": author_score,
            "media_score": media_score,
        }
        final_score = self._final_score(scores)

        return RankedItem(
            item=item,
            final_score=final_score,
            keyword_score=keyword_score,
            freshness_score=freshness_score,
            source_score=source_score,
            item_type_score=item_type_score,
            profile_score=profile_score,
            author_score=author_score,
            media_score=media_score,
            reasons=reasons,
        )

    def rank_items(
        self,
        items: list[ResearchItem],
        user_profile: str | None = None,
        keywords: list[str] | None = None,
        max_items: int | None = None,
        external_signals_by_url: dict[str, RankingExternalSignals] | None = None,
    ) -> list[RankedItem]:
        """Score and sort items by final_score descending."""
        if not items or max_items is not None and max_items <= 0:
            return []

        signals_by_url = external_signals_by_url or {}
        ranked_items = [
            self.score_item(
                item,
                user_profile=user_profile,
                keywords=keywords,
                external_signals=signals_by_url.get(item.url),
            )
            for item in items
        ]
        ranked_items.sort(key=lambda ranked: ranked.final_score, reverse=True)
        if max_items is not None:
            return ranked_items[:max_items]
        return ranked_items

    async def rank(self, items: list[ResearchItem], profile_id: str) -> list[ResearchItem]:
        """Compatibility wrapper for the original placeholder API."""
        return [ranked.item for ranked in self.rank_items(items, user_profile=profile_id)]

    def _keyword_score(self, item_text: str, keywords: list[str] | None, reasons: list[str]) -> float:
        normalized_keywords = self._unique_terms(keywords or [])
        if not normalized_keywords:
            return 0.0

        matches: list[str] = []
        for original, normalized in normalized_keywords:
            if self._contains_phrase(item_text, normalized):
                matches.append(original)
                reasons.append(f"Matched keyword: {original}")
        return self._clamp(len(matches) / len(normalized_keywords))

    def _profile_score(self, item_text: str, user_profile: str | None, reasons: list[str]) -> float:
        if not user_profile:
            return 0.0

        profile_tokens = self._tokenize(user_profile)
        if not profile_tokens:
            return 0.0

        item_tokens = set(self._tokenize(item_text))
        overlaps = sorted(token for token in profile_tokens if token in item_tokens)
        if overlaps:
            reasons.append(f"Profile overlap: {', '.join(overlaps[:5])}")
        return self._clamp(len(overlaps) / len(profile_tokens))

    def _freshness_score(self, item: ResearchItem, reasons: list[str]) -> float:
        if item.published_at is None:
            return 0.0

        published_at = self._as_utc(item.published_at)
        now = self._as_utc(self._now_provider())
        age_days = max(0.0, (now - published_at).total_seconds() / 86400)
        if age_days <= self.config.recent_item_days:
            reasons.append("Recent item")

        if self.config.freshness_window_days <= 0:
            return 0.0
        return self._clamp(1.0 - age_days / self.config.freshness_window_days)

    def _final_score(self, scores: dict[str, float]) -> float:
        total_weight = sum(max(0.0, weight) for weight in self.config.component_weights.values())
        if total_weight == 0:
            return 0.0

        weighted_sum = 0.0
        for score_name, score in scores.items():
            weighted_sum += self._clamp(score) * max(0.0, self.config.component_weights.get(score_name, 0.0))
        return round(self._clamp(weighted_sum / total_weight), 6)

    def _add_source_reasons(
        self,
        item: ResearchItem,
        source_score: float,
        item_type_score: float,
        reasons: list[str],
    ) -> None:
        if source_score >= 0.80:
            reasons.append(f"High-priority source: {item.source_name}")
        if item_type_score >= 0.80:
            reasons.append(f"High-priority item type: {item.item_type}")

    @staticmethod
    def _add_external_signal_reasons(
        author_score: float,
        media_score: float,
        external_signals: RankingExternalSignals | None,
        reasons: list[str],
    ) -> None:
        if author_score >= 0.70:
            reasons.append("High author authority signal")
        if media_score >= 0.70 or external_signals and external_signals.media_mentions:
            reasons.append("Mentioned by external media/news sources")

    @staticmethod
    def _item_text(item: ResearchItem) -> str:
        metadata_text = json.dumps(item.metadata or {}, ensure_ascii=False, sort_keys=True, default=str)
        parts = [
            item.title,
            item.abstract or "",
            item.raw_text or "",
            metadata_text,
        ]
        return " ".join(parts).lower()

    @classmethod
    def _unique_terms(cls, terms: list[str]) -> list[tuple[str, str]]:
        seen: set[str] = set()
        unique_terms: list[tuple[str, str]] = []
        for term in terms:
            original = " ".join(term.split())
            normalized = original.lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_terms.append((original, normalized))
        return unique_terms

    @classmethod
    def _tokenize(cls, text: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[\w.-]+", text.lower())
            if len(token) >= 2 and token not in STOPWORDS
        }
        expanded: set[str] = set(tokens)
        for token in tokens:
            expanded.update(part for part in re.split(r"[-_.]+", token) if len(part) >= 2 and part not in STOPWORDS)
        return expanded

    @classmethod
    def _contains_phrase(cls, item_text: str, phrase: str) -> bool:
        if phrase in item_text:
            return True
        expanded_text = re.sub(r"[-_]+", " ", item_text)
        expanded_phrase = re.sub(r"[-_]+", " ", phrase)
        return expanded_phrase in expanded_text

    @classmethod
    def _weighted_lookup(cls, key: str, weights: dict[str, float], default_score: float) -> float:
        return cls._clamp(weights.get(key.strip().lower(), default_score))

    @staticmethod
    def _signal_score(score: float | None) -> float:
        return RelevanceRankingService._clamp(score or 0.0)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


RelevanceRanker = RelevanceRankingService


__all__ = [
    "RankingConfig",
    "RankingExternalSignals",
    "RankedItem",
    "RelevanceRanker",
    "RelevanceRankingService",
]
