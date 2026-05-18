from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any, Protocol

from backend.services.ranking_service import RankingExternalSignals


@dataclass(frozen=True)
class AuthorSignal:
    """Deterministic author authority signal for ranking."""

    first_author: str | None
    senior_author: str | None
    corresponding_author: str | None
    first_author_citations: float
    senior_author_citations: float
    first_author_h_index: float
    senior_author_h_index: float
    author_score: float
    raw_metrics: dict[str, Any]


class AuthorMetricsProvider(Protocol):
    """Provider abstraction for future Semantic Scholar/OpenAlex/Scholar metrics."""

    def get_author_metrics(
        self,
        title: str | None,
        authors: list[str],
        external_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        """Return metrics keyed by author name."""


class MetadataAuthorMetricsProvider:
    """Read deterministic author metrics from item metadata."""

    def get_author_metrics(
        self,
        title: str | None,
        authors: list[str],
        external_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        del title, external_id
        metadata = metadata or {}
        metrics = metadata.get("author_metrics")
        if isinstance(metrics, dict):
            return {
                str(author): metric
                for author, metric in metrics.items()
                if isinstance(metric, dict)
            }

        author_records = metadata.get("authors")
        if isinstance(author_records, list):
            return self._metrics_from_author_records(author_records)

        return {author: {} for author in authors}

    @staticmethod
    def _metrics_from_author_records(author_records: list[Any]) -> dict[str, dict[str, Any]]:
        metrics: dict[str, dict[str, Any]] = {}
        for record in author_records:
            if not isinstance(record, dict):
                continue
            name = record.get("name") or record.get("author") or record.get("full_name")
            if name:
                metrics[str(name)] = dict(record)
        return metrics


class AuthorSignalService:
    """Build lightweight author authority signals without external API calls."""

    def __init__(self, provider: AuthorMetricsProvider | None = None) -> None:
        self.provider = provider or MetadataAuthorMetricsProvider()

    def get_signal(
        self,
        title: str | None,
        authors: list[str],
        external_id: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> AuthorSignal:
        """Extract author roles and score provided author metrics."""
        normalized_authors = [author.strip() for author in authors if author and author.strip()]
        first_author = normalized_authors[0] if normalized_authors else None
        senior_author = normalized_authors[-1] if normalized_authors else None
        corresponding_author = self._corresponding_author(metadata, senior_author)

        raw_metrics = self.provider.get_author_metrics(title, normalized_authors, external_id, metadata)
        first_metrics = self._metrics_for(first_author, raw_metrics)
        senior_metrics = self._metrics_for(senior_author, raw_metrics)

        first_citations = self._metric_number(first_metrics, "citations", "citation_count", "total_citations")
        senior_citations = self._metric_number(senior_metrics, "citations", "citation_count", "total_citations")
        first_h_index = self._metric_number(first_metrics, "h_index", "hIndex", "hindex")
        senior_h_index = self._metric_number(senior_metrics, "h_index", "hIndex", "hindex")
        author_score = self._combined_author_score(
            first_citations,
            first_h_index,
            senior_citations,
            senior_h_index,
        )

        return AuthorSignal(
            first_author=first_author,
            senior_author=senior_author,
            corresponding_author=corresponding_author,
            first_author_citations=first_citations,
            senior_author_citations=senior_citations,
            first_author_h_index=first_h_index,
            senior_author_h_index=senior_h_index,
            author_score=author_score,
            raw_metrics=raw_metrics,
        )

    @classmethod
    def _combined_author_score(
        cls,
        first_citations: float,
        first_h_index: float,
        senior_citations: float,
        senior_h_index: float,
    ) -> float:
        first_score = cls._single_author_score(first_citations, first_h_index)
        senior_score = cls._single_author_score(senior_citations, senior_h_index)
        if first_score and senior_score:
            return cls._clamp(0.45 * first_score + 0.55 * senior_score)
        return cls._clamp(first_score or senior_score)

    @classmethod
    def _single_author_score(cls, citations: float, h_index: float) -> float:
        citation_score = cls._citation_score(citations)
        h_index_score = cls._h_index_score(h_index)
        return cls._clamp(0.60 * citation_score + 0.40 * h_index_score)

    @staticmethod
    def _citation_score(citations: float) -> float:
        if citations <= 0:
            return 0.0
        return AuthorSignalService._clamp(log10(citations + 1.0) / 5.0)

    @staticmethod
    def _h_index_score(h_index: float) -> float:
        return AuthorSignalService._clamp(h_index / 100.0)

    @staticmethod
    def _corresponding_author(metadata: dict[str, Any] | None, fallback: str | None) -> str | None:
        metadata = metadata or {}
        candidates = [
            metadata.get("corresponding_author"),
            metadata.get("corresponding"),
            metadata.get("corresponding_authors"),
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, list) and candidate:
                first = candidate[0]
                if isinstance(first, str) and first.strip():
                    return first.strip()
                if isinstance(first, dict):
                    name = first.get("name") or first.get("author") or first.get("full_name")
                    if name:
                        return str(name).strip()

        for record in metadata.get("authors", []) if isinstance(metadata.get("authors"), list) else []:
            if not isinstance(record, dict) or not record.get("is_corresponding"):
                continue
            name = record.get("name") or record.get("author") or record.get("full_name")
            if name:
                return str(name).strip()

        return fallback

    @staticmethod
    def _metrics_for(author: str | None, raw_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not author:
            return {}
        if author in raw_metrics:
            return raw_metrics[author]
        normalized_author = author.strip().lower()
        for metric_author, metrics in raw_metrics.items():
            if metric_author.strip().lower() == normalized_author:
                return metrics
        return {}

    @staticmethod
    def _metric_number(metrics: dict[str, Any], *keys: str) -> float:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, (int, float)):
                return max(0.0, float(value))
            if isinstance(value, str):
                try:
                    return max(0.0, float(value.replace(",", "")))
                except ValueError:
                    continue
        return 0.0

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))


def to_ranking_external_signals(
    author_signal: AuthorSignal | None = None,
    media_signal: Any | None = None,
) -> RankingExternalSignals:
    """Convert optional authority and media signals into ranking inputs."""
    return RankingExternalSignals(
        author_score=author_signal.author_score if author_signal else None,
        media_score=getattr(media_signal, "media_score", None) if media_signal else None,
        author_metrics=author_signal.raw_metrics if author_signal else None,
        media_mentions=getattr(media_signal, "mentions", None) if media_signal else None,
    )


__all__ = [
    "AuthorMetricsProvider",
    "AuthorSignal",
    "AuthorSignalService",
    "MetadataAuthorMetricsProvider",
    "to_ranking_external_signals",
]
