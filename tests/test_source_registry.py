from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.collectors.base import ResearchItem
from backend.services.source_registry import SourceRegistry


def make_item(
    title: str,
    url: str,
    item_type: str,
    source_type: str | None = None,
    metadata: dict[str, object] | None = None,
    keywords: list[str] | None = None,
) -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract="A useful web discovery result.",
        url=url,
        source_name="web",
        source_type=source_type or item_type,
        item_type=item_type,
        authors=[],
        published_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        raw_text="A useful web discovery result.",
        external_id=url,
        keywords=keywords or [],
        metadata=metadata or {},
    )


def test_source_registry_add_source_creates_registry_file(tmp_path: Path) -> None:
    path = tmp_path / "source_registry.json"
    registry = SourceRegistry(path)
    record = registry.build_record(
        name="Nature Single Cell",
        url="https://www.nature.com/subjects/single-cell-analysis",
        source_type="website",
        tags=["single-cell", "nature"],
    )

    change = registry.add_or_update(record)

    assert change.status == "added"
    assert path.exists()
    loaded = registry.load()
    assert len(loaded) == 1
    assert loaded[0].name == "Nature Single Cell"
    assert loaded[0].domain == "nature.com"
    assert loaded[0].tags == ["single-cell", "nature"]


def test_source_registry_adding_same_url_updates_existing_source(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    first = registry.build_record(
        name="Old Name",
        url="https://example.com/page?utm_source=newsletter",
        source_type="blog",
        tags=["old"],
    )
    second = registry.build_record(
        name="New Name",
        url="http://example.com/page/?utm_campaign=lab",
        source_type="blog",
        tags=["new"],
        priority=2.0,
    )

    assert registry.add_or_update(first).status == "added"
    change = registry.add_or_update(second)

    records = registry.load()
    assert change.status == "updated"
    assert len(records) == 1
    assert records[0].name == "New Name"
    assert records[0].url == "https://example.com/page"
    assert records[0].priority == 2.0
    assert records[0].tags == ["old", "new"]


def test_source_registry_blocked_domain_prevents_adding(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    registry.block_domain("reddit.com")
    record = registry.build_record(
        name="Blocked source",
        url="https://www.reddit.com/r/MachineLearning/",
        source_type="blog",
    )

    change = registry.add_or_update(record)

    assert change.status == "blocked"
    assert registry.load() == []
    assert registry.is_domain_blocked("old.reddit.com")


def test_source_registry_list_enabled_filters_disabled_sources(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    enabled = registry.build_record(name="Enabled", url="https://example.com/news", source_type="news")
    disabled = registry.build_record(
        name="Disabled",
        url="https://disabled.example.com/blog",
        source_type="blog",
        enabled=False,
    )
    registry.add_or_update(enabled)
    registry.add_or_update(disabled)

    enabled_records = registry.list_enabled()
    blog_records = registry.list_enabled("blog")

    assert [record.name for record in enabled_records] == ["Enabled"]
    assert blog_records == []


def test_source_registry_import_from_web_results_registers_useful_source_types(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    items = [
        make_item("Dataset", "https://zenodo.org/records/1", "dataset", keywords=["single-cell"]),
        make_item("News", "https://example-news.com/news/model", "news"),
        make_item("Blog", "https://example-blog.com/blog/model", "blog"),
        make_item("Lab", "https://lab.example.edu/group/update", "lab_page"),
        make_item("Company Research", "https://research.example.com/research/model", "company_research"),
        make_item("Generic page", "https://random.example.com/page", "webpage", source_type="web"),
    ]

    summary = registry.import_from_web_results(items)

    records = registry.load()
    assert summary.new_sources_added == 5
    assert summary.existing_sources_updated == 0
    assert summary.blocked_domains_skipped == 0
    assert summary.candidates_considered == 5
    assert {record.source_type for record in records} == {
        "dataset",
        "news",
        "blog",
        "lab_page",
        "company_research",
    }
    assert "random.example.com" not in {record.domain for record in records}


def test_source_registry_import_from_web_results_registers_discovered_rss_feeds(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    item = make_item(
        "Lab update",
        "https://example.edu/group/update",
        "lab_page",
        metadata={"discovered_feeds": ["https://example.edu/feed.xml", "https://example.edu/feed.xml?utm_source=x"]},
    )

    summary = registry.import_from_web_results([item])

    records = registry.load()
    rss_records = [record for record in records if record.source_type == "rss"]
    assert summary.new_sources_added == 2
    assert len(rss_records) == 1
    assert rss_records[0].url == "https://example.edu/feed.xml"
    assert rss_records[0].metadata["parent_url"] == "https://example.edu/group/update"


def test_source_registry_export_document_includes_blocked_domains(tmp_path: Path) -> None:
    registry = SourceRegistry(tmp_path / "source_registry.json")
    registry.block_domain("reddit.com")

    document = json.loads((tmp_path / "source_registry.json").read_text(encoding="utf-8"))

    assert document["blocked_domains"] == ["reddit.com"]
    assert registry.export_document()["blocked_domains"] == ["reddit.com"]
