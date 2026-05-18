from datetime import datetime, timedelta, timezone

from backend.collectors.base import ResearchItem
from backend.services.ranking_service import (
    RankingExternalSignals,
    RelevanceRankingService,
)


NOW = datetime(2026, 5, 18, tzinfo=timezone.utc)


def make_service() -> RelevanceRankingService:
    return RelevanceRankingService(now_provider=lambda: NOW)


def make_item(
    title: str = "Single-cell graph agent method",
    abstract: str | None = "A retrieval method for single-cell graph learning.",
    url: str = "https://example.com/item",
    source_name: str = "arxiv",
    item_type: str = "paper",
    published_at: datetime | None = NOW - timedelta(days=2),
    raw_text: str | None = "The method improves retrieval and agent memory.",
    metadata: dict[str, object] | None = None,
) -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract=abstract,
        url=url,
        source_name=source_name,
        source_type="paper" if item_type == "paper" else "code",
        item_type=item_type,
        authors=["Ada Lovelace"],
        published_at=published_at,
        raw_text=raw_text,
        external_id="test-id",
        keywords=[],
        metadata=metadata or {"domain": "single-cell", "task": "retrieval"},
    )


def test_keyword_scoring_matches_item_text_and_metadata() -> None:
    ranked = make_service().score_item(
        make_item(),
        keywords=["single-cell", "retrieval", "missing"],
    )

    assert ranked.keyword_score == 2 / 3
    assert "Matched keyword: single-cell" in ranked.reasons
    assert "Matched keyword: retrieval" in ranked.reasons


def test_freshness_scoring_prefers_newer_items() -> None:
    service = make_service()
    recent = service.score_item(make_item(published_at=NOW - timedelta(days=3)))
    old = service.score_item(make_item(url="https://example.com/old", published_at=NOW - timedelta(days=300)))

    assert recent.freshness_score > old.freshness_score
    assert "Recent item" in recent.reasons
    assert "Recent item" not in old.reasons


def test_rank_items_sorts_by_final_score_descending() -> None:
    service = make_service()
    matching = make_item(title="Graph retrieval for agents", url="https://example.com/matching")
    non_matching = make_item(
        title="Unrelated database note",
        abstract="A short operational update.",
        url="https://example.com/non-matching",
        source_name="rss",
        item_type="news",
        raw_text="No relevant method details.",
        metadata={},
    )

    ranked = service.rank_items([non_matching, matching], keywords=["graph", "retrieval"])

    assert [item.item.url for item in ranked] == ["https://example.com/matching", "https://example.com/non-matching"]
    assert ranked[0].final_score >= ranked[1].final_score


def test_rank_items_respects_max_items() -> None:
    service = make_service()
    items = [make_item(title=f"Paper {index}", url=f"https://example.com/{index}") for index in range(3)]

    ranked = service.rank_items(items, max_items=2)

    assert len(ranked) == 2


def test_rank_items_empty_input() -> None:
    assert make_service().rank_items([]) == []


def test_missing_metadata_and_published_at_fallback() -> None:
    ranked = make_service().score_item(
        make_item(
            abstract=None,
            published_at=None,
            raw_text=None,
            metadata={},
        ),
        keywords=[],
    )

    assert ranked.keyword_score == 0.0
    assert ranked.profile_score == 0.0
    assert ranked.freshness_score == 0.0
    assert 0.0 <= ranked.final_score <= 1.0


def test_author_score_affects_final_score_when_external_signal_is_provided() -> None:
    service = make_service()
    item = make_item()

    without_signal = service.score_item(item)
    with_signal = service.score_item(item, external_signals=RankingExternalSignals(author_score=1.0))

    assert with_signal.author_score == 1.0
    assert with_signal.final_score > without_signal.final_score
    assert "High author authority signal" in with_signal.reasons


def test_media_score_affects_final_score_when_external_signal_is_provided() -> None:
    service = make_service()
    item = make_item()

    without_signal = service.score_item(item)
    with_signal = service.score_item(
        item,
        external_signals=RankingExternalSignals(
            media_score=1.0,
            media_mentions=[{"source": "example-news"}],
        ),
    )

    assert with_signal.media_score == 1.0
    assert with_signal.final_score > without_signal.final_score
    assert "Mentioned by external media/news sources" in with_signal.reasons


def test_profile_score_uses_lexical_overlap() -> None:
    ranked = make_service().score_item(
        make_item(title="Graph retrieval agent memory"),
        user_profile="graph retrieval systems",
    )

    assert ranked.profile_score == 2 / 3
    assert "Profile overlap: graph, retrieval" in ranked.reasons
