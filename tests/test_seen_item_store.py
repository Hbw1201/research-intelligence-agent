from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.collectors.base import ResearchItem
from backend.services.item_fingerprint import (
    item_fingerprint,
    normalize_canonical_url,
    normalize_title,
)
from backend.services.seen_item_store import SeenItemStore


def make_item(
    title: str,
    url: str,
    external_id: str | None = None,
    source_name: str = "web",
    item_type: str = "webpage",
    metadata: dict[str, object] | None = None,
) -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract="A relevant research update.",
        url=url,
        source_name=source_name,
        source_type="web",
        item_type=item_type,
        authors=[],
        published_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        raw_text="A relevant research update.",
        external_id=external_id,
        keywords=[],
        metadata=metadata or {},
    )


def test_tracking_params_do_not_create_new_fingerprints() -> None:
    first = make_item("Tracking", "http://example.com/page/?utm_source=newsletter&x=1&fbclid=abc#section")
    second = make_item("Tracking", "https://example.com/page?x=1&utm_campaign=lab&ref=twitter")

    assert item_fingerprint(first) == item_fingerprint(second)
    assert normalize_canonical_url(first.url) == "https://example.com/page?x=1"


def test_same_github_repo_url_deduplicates() -> None:
    first = make_item(
        "Owner/Repo",
        "https://github.com/Owner/Repo?utm_source=newsletter",
        source_name="github",
        item_type="repository",
    )
    second = make_item(
        "different title",
        "http://github.com/owner/repo/",
        source_name="github",
        item_type="repository",
    )

    assert item_fingerprint(first) == "github:owner/repo"
    assert item_fingerprint(first) == item_fingerprint(second)


def test_same_pubmed_id_deduplicates() -> None:
    first = make_item(
        "PubMed article",
        "https://pubmed.ncbi.nlm.nih.gov/123456/",
        external_id="123456",
        source_name="pubmed",
        item_type="paper",
    )
    second = make_item(
        "PubMed article duplicate",
        "https://example.com/article",
        source_name="pubmed",
        item_type="paper",
        metadata={"pmid": "PMID: 123456"},
    )

    assert item_fingerprint(first) == "pmid:123456"
    assert item_fingerprint(first) == item_fingerprint(second)


def test_doi_has_fingerprint_priority() -> None:
    item = make_item(
        "DOI article",
        "https://pubmed.ncbi.nlm.nih.gov/123456/",
        external_id="123456",
        source_name="pubmed",
        item_type="paper",
        metadata={"doi": "https://doi.org/10.1000/Test.DOI"},
    )

    assert item_fingerprint(item) == "doi:10.1000/test.doi"


def test_title_fallback_normalization_removes_safe_punctuation() -> None:
    assert normalize_title("  Graph-Agent: Memory, Retrieval!  ") == "graph agent memory retrieval"


def test_seen_store_writes_jsonl_records(tmp_path: Path) -> None:
    store_path = tmp_path / "seen_items.jsonl"
    item = make_item("JSONL item", "https://example.com/jsonl")
    store = SeenItemStore(store_path)

    store.mark_seen([item], pushed=False)

    records = [json.loads(line) for line in store_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["fingerprint"] == "url:https://example.com/jsonl"
    assert records[0]["pushed"] is False
    assert records[0]["title"] == "JSONL item"
    assert store.load_seen() == {"url:https://example.com/jsonl"}


def test_seen_store_allows_later_pushed_record(tmp_path: Path) -> None:
    store_path = tmp_path / "seen_items.jsonl"
    item = make_item("Push item", "https://example.com/push")
    store = SeenItemStore(store_path)

    store.mark_seen([item], pushed=False)
    store.mark_seen([item], pushed=True)

    records = [json.loads(line) for line in store_path.read_text(encoding="utf-8").splitlines()]
    assert [record["pushed"] for record in records] == [False, True]
    assert store.load_seen() == {"url:https://example.com/push"}
