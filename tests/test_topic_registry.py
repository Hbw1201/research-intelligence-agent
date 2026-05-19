from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.collectors.base import ResearchItem
from backend.services.topic_registry import HotspotDiscoveryService, TopicRegistry, detect_language


def make_item(
    title: str,
    abstract: str = "",
    source_name: str = "web",
    keywords: list[str] | None = None,
    metadata: dict[str, object] | None = None,
) -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract=abstract,
        url=f"https://example.com/{abs(hash(title))}",
        source_name=source_name,
        source_type="web",
        item_type="webpage",
        authors=[],
        published_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        raw_text=abstract,
        external_id=None,
        keywords=keywords or [],
        metadata=metadata or {},
    )


def test_topic_registry_loads_bilingual_seed_topics(tmp_path: Path) -> None:
    registry = TopicRegistry(tmp_path / "topic_registry.json")

    topics = {record.topic for record in registry.load()}

    assert "AI for biology" in topics
    assert "single-cell foundation model" in topics
    assert "生信 大模型" in topics
    assert "空间转录组" in topics
    assert detect_language("空间转录组") == "zh"
    assert detect_language("AI 生信") == "mixed"


def test_topic_registry_add_update_disable_and_export(tmp_path: Path) -> None:
    registry = TopicRegistry(tmp_path / "topic_registry.json")
    first = registry.build_record("cell atlas foundation model", aliases=["cell atlas FM"], score=0.4)
    second = registry.build_record("cell atlas FM", aliases=["atlas model"], score=0.3)

    assert registry.add_or_update(first).status == "added"
    assert registry.add_or_update(second).status == "updated"
    assert registry.disable("atlas model") is True

    records = [record for record in registry.load() if record.topic == "cell atlas foundation model"]
    assert len(records) == 1
    assert records[0].enabled is False
    assert records[0].score == 0.7
    document = registry.export_document()
    assert any(record["topic"] == "cell atlas foundation model" for record in document["topics"])
    assert json.loads((tmp_path / "topic_registry.json").read_text(encoding="utf-8"))["topics"]


def test_hotspot_discovery_extracts_candidates_from_item_text_and_metadata(tmp_path: Path) -> None:
    registry = TopicRegistry(tmp_path / "topic_registry.json")
    service = HotspotDiscoveryService(topic_registry=registry, min_score=0.2, max_topics=10)
    items = [
        make_item(
            "Single-cell foundation model improves perturbation prediction",
            abstract="A virtual cell model for drug response and perturbation response prediction.",
            source_name="web",
            metadata={"snippet": "single-cell foundation model benchmark", "tags": ["AI for biology"]},
        ),
        make_item(
            "单细胞 基础模型 用于 扰动预测",
            abstract="空间转录组 与 药物反应 分析",
            source_name="rss",
        ),
    ]

    candidates = service.extract_candidates(items)

    topics = {candidate.topic for candidate in candidates}
    assert "single-cell foundation model" in topics
    assert "perturbation prediction" in topics
    assert "drug response" in topics
    assert "单细胞 基础模型" in topics
    assert "扰动预测" in topics
    assert all(candidate.score >= 0.2 for candidate in candidates)


def test_hotspot_discovery_updates_registry_counts(tmp_path: Path) -> None:
    registry = TopicRegistry(tmp_path / "topic_registry.json")
    service = HotspotDiscoveryService(topic_registry=registry, min_score=0.2, max_topics=10)
    items = [
        make_item("Bioinformatics foundation model for genomics", source_name="web"),
        make_item("Bioinformatics foundation model benchmark", source_name="rss"),
    ]

    summary = service.update_registry(items)

    records = [record for record in registry.load() if record.topic == "bioinformatics foundation model"]
    assert summary.candidates_considered >= 1
    assert summary.existing_topics_updated >= 1
    assert records[0].item_count >= 2
    assert records[0].source_count >= 2


def test_topic_registry_list_enabled_filters_min_score_and_disabled(tmp_path: Path) -> None:
    registry = TopicRegistry(tmp_path / "topic_registry.json")
    registry.add_or_update(registry.build_record("rare AI biology topic", score=0.3))
    registry.add_or_update(registry.build_record("disabled AI biology topic", score=0.9, enabled=False))

    topics = {record.topic for record in registry.list_enabled(min_score=0.8)}

    assert "disabled AI biology topic" not in topics
    assert all(record.score >= 0.8 for record in registry.list_enabled(min_score=0.8))
