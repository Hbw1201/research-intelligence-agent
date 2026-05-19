from __future__ import annotations

from datetime import datetime, timezone

from backend.services.topic_registry import TopicRecord
from backend.search.web_query_planner import WebQueryPlanner


class FakeTopicRegistry:
    def __init__(self, topics: list[TopicRecord]) -> None:
        self.topics = topics
        self.calls: list[dict[str, object]] = []

    def list_enabled(self, min_score: float = 0.0, limit: int | None = None) -> list[TopicRecord]:
        self.calls.append({"min_score": min_score, "limit": limit})
        records = [topic for topic in self.topics if topic.enabled and topic.score >= min_score]
        return records[:limit] if limit is not None else records


def topic_record(topic: str, score: float = 0.8) -> TopicRecord:
    now = datetime(2026, 5, 19, tzinfo=timezone.utc)
    return TopicRecord(
        topic=topic,
        language="en",
        aliases=[],
        score=score,
        first_seen_at=now,
        last_seen_at=now,
        source_count=1,
        item_count=1,
        enabled=True,
    )


def test_query_planner_expands_keyword_string_into_multiple_categories() -> None:
    planner = WebQueryPlanner(
        categories=["general", "news", "blog", "dataset", "benchmark", "code"],
        max_queries=10,
    )

    queries = planner.plan("single-cell foundation model perturbation prediction drug response")

    assert "single-cell foundation model perturbation prediction drug response" in queries
    assert "single-cell foundation model perturbation prediction drug response benchmark" in queries
    assert "single-cell foundation model perturbation prediction drug response dataset" in queries
    assert "single-cell foundation model perturbation prediction drug response blog" in queries
    assert "single-cell foundation model perturbation prediction drug response news" in queries
    assert "single-cell foundation model drug response GitHub" in queries


def test_query_planner_includes_profile_terms_without_duplicate_queries() -> None:
    planner = WebQueryPlanner(categories=["general"], max_queries=5)

    planned = planner.plan_with_categories(
        ["single-cell", "drug response"],
        user_profile="Interested in BioPatchFM and BioPatchFM updates.",
    )

    assert planned[0].query == "single-cell drug response"
    assert any(query.query.startswith("BioPatchFM single-cell drug response") for query in planned)
    assert len({query.query.lower() for query in planned}) == len(planned)


def test_query_planner_uses_topic_registry_when_enabled() -> None:
    registry = FakeTopicRegistry([topic_record("virtual cell"), topic_record("spatial transcriptomics", score=0.1)])
    planner = WebQueryPlanner(
        categories=["general"],
        max_queries=5,
        topic_registry=registry,
        use_topic_registry=True,
        topic_min_score=0.2,
        topic_limit=3,
    )

    planned = planner.plan_with_categories("single-cell foundation model")

    assert registry.calls == [{"min_score": 0.2, "limit": 3}]
    assert "single-cell foundation model" in [query.query for query in planned]
    assert "virtual cell" in [query.query for query in planned]
    assert all("spatial transcriptomics" not in query.query for query in planned)
    assert any(query.category == "hotspot" for query in planned)
