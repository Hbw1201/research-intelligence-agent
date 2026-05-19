from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


DEFAULT_QUERY_CATEGORIES = [
    "general",
    "news",
    "blog",
    "dataset",
    "benchmark",
    "lab",
    "company_research",
]


@dataclass(frozen=True)
class PlannedWebQuery:
    """Search query with the broad-discovery category that produced it."""

    query: str
    category: str


class TopicRegistryProtocol:
    """Small protocol-like surface used to avoid coupling planner to storage details."""

    def list_enabled(self, min_score: float = 0.0, limit: int | None = None) -> list[Any]:
        """Return enabled topic records."""


class WebQueryPlanner:
    """Create a bounded set of broad web-discovery queries."""

    def __init__(
        self,
        categories: list[str] | None = None,
        max_queries: int = 10,
        topic_registry: TopicRegistryProtocol | None = None,
        use_topic_registry: bool = False,
        topic_min_score: float = 0.2,
        topic_limit: int = 8,
    ) -> None:
        self.categories = self._normalize_categories(categories or DEFAULT_QUERY_CATEGORIES)
        self.max_queries = max(1, max_queries)
        self.topic_registry = topic_registry
        self.use_topic_registry = use_topic_registry
        self.topic_min_score = max(0.0, topic_min_score)
        self.topic_limit = max(0, topic_limit)

    def plan(self, keywords: str | list[str], user_profile: str | None = None) -> list[str]:
        """Return planned query strings for compatibility with simple callers."""
        return [planned.query for planned in self.plan_with_categories(keywords, user_profile=user_profile)]

    def plan_with_categories(
        self,
        keywords: str | list[str],
        user_profile: str | None = None,
    ) -> list[PlannedWebQuery]:
        """Return planned queries and their source categories."""
        base_query = self._normalize_keywords(keywords)
        if not base_query:
            return []

        profile_terms = self._profile_terms(user_profile)
        planned: list[PlannedWebQuery] = []
        seen: set[str] = set()

        def add(query: str, category: str) -> None:
            normalized = " ".join(query.split())
            key = normalized.lower()
            if not normalized or key in seen or len(planned) >= self.max_queries:
                return
            planned.append(PlannedWebQuery(query=normalized, category=category))
            seen.add(key)

        for category in self.categories:
            if category == "general":
                add(base_query, category)
            elif category == "news":
                add(f"{base_query} news", category)
                add(f"{self._focused_query(base_query, 4)} lab news", category)
            elif category == "blog":
                add(f"{base_query} blog", category)
            elif category == "dataset":
                add(f"{base_query} dataset", category)
            elif category == "benchmark":
                add(f"{base_query} benchmark", category)
            elif category == "code":
                add(f"{self._head_tail_query(base_query)} GitHub", category)
            elif category == "lab":
                add(f"{self._focused_query(base_query, 4)} lab", category)
            elif category == "company_research":
                add(f"{self._head_tail_query(base_query)} research blog", category)
                add(f"{self._head_tail_query(base_query)} company research", category)
            elif category == "preprint":
                add(f"{base_query} preprint", category)
            elif category == "method":
                add(f"{base_query} method", category)

        for term in profile_terms:
            add(f"{term} {self._head_tail_query(base_query)}", "general")

        for topic in self._registry_topics():
            if self._topic_matches_query(topic, base_query):
                add(f"{topic.topic} {self._head_tail_query(base_query)}", "hotspot")
            else:
                add(topic.topic, "hotspot")

        return planned

    @staticmethod
    def _normalize_keywords(keywords: str | list[str]) -> str:
        if isinstance(keywords, str):
            text = keywords
        else:
            text = " ".join(str(keyword) for keyword in keywords)
        return " ".join(text.split())

    @staticmethod
    def _normalize_categories(categories: list[str]) -> list[str]:
        allowed = {
            "general",
            "news",
            "blog",
            "dataset",
            "benchmark",
            "code",
            "lab",
            "company_research",
            "preprint",
            "method",
        }
        normalized: list[str] = []
        seen: set[str] = set()
        for category in categories:
            value = category.strip().lower()
            if value in allowed and value not in seen:
                normalized.append(value)
                seen.add(value)
        return normalized or ["general"]

    @staticmethod
    def _focused_query(base_query: str, max_terms: int) -> str:
        terms = base_query.split()
        if len(terms) <= max_terms:
            return base_query
        return " ".join(terms[:max_terms])

    @staticmethod
    def _head_tail_query(base_query: str) -> str:
        terms = base_query.split()
        if len(terms) <= 5:
            return base_query
        return " ".join([*terms[:3], *terms[-2:]])

    @staticmethod
    def _profile_terms(user_profile: str | None) -> list[str]:
        if not user_profile:
            return []
        candidates = re.findall(r"[A-Z][A-Za-z0-9-]{2,}", user_profile)
        seen: set[str] = set()
        terms: list[str] = []
        for candidate in candidates:
            key = candidate.lower()
            if key not in seen:
                terms.append(candidate)
                seen.add(key)
        return terms[:2]

    def _registry_topics(self) -> list[Any]:
        if not self.use_topic_registry or self.topic_registry is None or self.topic_limit <= 0:
            return []
        return self.topic_registry.list_enabled(min_score=self.topic_min_score, limit=self.topic_limit)

    @staticmethod
    def _topic_matches_query(topic: Any, base_query: str) -> bool:
        text = base_query.casefold()
        candidates = [topic.topic, *topic.aliases]
        return any(candidate.casefold() in text for candidate in candidates)


__all__ = ["DEFAULT_QUERY_CATEGORIES", "PlannedWebQuery", "TopicRegistryProtocol", "WebQueryPlanner"]
