from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from math import log2
from typing import Any, Callable, Protocol


DEFAULT_HIGH_QUALITY_SOURCES = {
    "acm technews",
    "cell",
    "ieee spectrum",
    "mit technology review",
    "nature",
    "nejm",
    "science",
    "stat",
    "the lancet",
}


@dataclass(frozen=True)
class MediaSignal:
    """Deterministic media/news attention signal for ranking."""

    mention_count: int
    high_quality_mention_count: int
    source_names: list[str]
    media_score: float
    mentions: list[dict[str, Any]]


class MediaMentionsProvider(Protocol):
    """Provider abstraction for future GDELT/NewsAPI/Google News RSS/SerpAPI sources."""

    def get_mentions(
        self,
        title: str,
        url: str | None,
        external_id: str | None,
        keywords: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Return media mentions for a research item."""


class EmptyMediaMentionsProvider:
    """Default provider that intentionally performs no external lookups."""

    def get_mentions(
        self,
        title: str,
        url: str | None,
        external_id: str | None,
        keywords: list[str] | None,
    ) -> list[dict[str, Any]]:
        del title, url, external_id, keywords
        return []


class MediaSignalService:
    """Build lightweight media attention signals without external API calls."""

    def __init__(
        self,
        provider: MediaMentionsProvider | None = None,
        high_quality_sources: set[str] | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.provider = provider or EmptyMediaMentionsProvider()
        self.high_quality_sources = {
            self._normalize_source(source) for source in (high_quality_sources or DEFAULT_HIGH_QUALITY_SOURCES)
        }
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_signal(
        self,
        title: str,
        url: str | None = None,
        external_id: str | None = None,
        keywords: list[str] | None = None,
    ) -> MediaSignal:
        """Score provided media mentions deterministically."""
        mentions = [dict(mention) for mention in self.provider.get_mentions(title, url, external_id, keywords)]
        source_names = self._source_names(mentions)
        high_quality_count = sum(1 for mention in mentions if self._is_high_quality_source(self._source_name(mention)))
        media_score = self._media_score(mentions, high_quality_count)

        return MediaSignal(
            mention_count=len(mentions),
            high_quality_mention_count=high_quality_count,
            source_names=source_names,
            media_score=media_score,
            mentions=mentions,
        )

    def _media_score(self, mentions: list[dict[str, Any]], high_quality_count: int) -> float:
        mention_count = len(mentions)
        if mention_count == 0:
            return 0.0

        count_score = self._clamp(log2(mention_count + 1.0) / 5.0)
        quality_score = self._clamp(high_quality_count / mention_count)
        recency_score = self._recency_score(mentions)
        return self._clamp(0.45 * count_score + 0.35 * quality_score + 0.20 * recency_score)

    def _recency_score(self, mentions: list[dict[str, Any]]) -> float:
        mention_scores: list[float] = []
        now = self._as_utc(self._now_provider())
        for mention in mentions:
            published_at = self._published_at(mention)
            if published_at is None:
                continue
            age_days = max(0.0, (now - published_at).total_seconds() / 86400)
            mention_scores.append(self._clamp(1.0 - age_days / 90.0))
        if not mention_scores:
            return 0.0
        return sum(mention_scores) / len(mention_scores)

    def _is_high_quality_source(self, source_name: str | None) -> bool:
        normalized = self._normalize_source(source_name or "")
        if not normalized:
            return False
        return any(source == normalized or source in normalized for source in self.high_quality_sources)

    @classmethod
    def _source_names(cls, mentions: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for mention in mentions:
            name = cls._source_name(mention)
            normalized = cls._normalize_source(name or "")
            if name and normalized not in seen:
                seen.add(normalized)
                names.append(name)
        return names

    @staticmethod
    def _source_name(mention: dict[str, Any]) -> str | None:
        source = mention.get("source_name") or mention.get("source") or mention.get("publisher")
        if isinstance(source, dict):
            source = source.get("name")
        return str(source).strip() if source else None

    @staticmethod
    def _published_at(mention: dict[str, Any]) -> datetime | None:
        value = mention.get("published_at") or mention.get("published") or mention.get("date")
        if isinstance(value, datetime):
            return MediaSignalService._as_utc(value)
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
        if isinstance(value, str) and value.strip():
            text = value.strip().replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            return MediaSignalService._as_utc(parsed)
        return None

    @staticmethod
    def _normalize_source(source: str) -> str:
        return " ".join(source.lower().split())

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


__all__ = [
    "DEFAULT_HIGH_QUALITY_SOURCES",
    "EmptyMediaMentionsProvider",
    "MediaMentionsProvider",
    "MediaSignal",
    "MediaSignalService",
]
