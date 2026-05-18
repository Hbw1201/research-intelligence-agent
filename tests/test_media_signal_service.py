from datetime import datetime, timedelta, timezone
from typing import Any

from backend.services.media_signal_service import MediaSignalService


NOW = datetime(2026, 5, 18, tzinfo=timezone.utc)


class FakeMediaMentionsProvider:
    def __init__(self, mentions: list[dict[str, Any]]) -> None:
        self.mentions = mentions
        self.calls: list[dict[str, Any]] = []

    def get_mentions(
        self,
        title: str,
        url: str | None,
        external_id: str | None,
        keywords: list[str] | None,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "title": title,
                "url": url,
                "external_id": external_id,
                "keywords": keywords,
            }
        )
        return self.mentions


def make_service(mentions: list[dict[str, Any]]) -> tuple[MediaSignalService, FakeMediaMentionsProvider]:
    provider = FakeMediaMentionsProvider(mentions)
    service = MediaSignalService(provider=provider, now_provider=lambda: NOW)
    return service, provider


def test_media_score_from_mocked_mentions() -> None:
    service, provider = make_service(
        [
            {"source_name": "Example News", "published_at": NOW - timedelta(days=1)},
            {"source_name": "Example Blog", "published_at": NOW - timedelta(days=10)},
        ]
    )

    signal = service.get_signal(
        title="Graph agent breakthrough",
        url="https://example.com/item",
        external_id="paper-1",
        keywords=["graph", "agent"],
    )

    assert signal.mention_count == 2
    assert signal.high_quality_mention_count == 0
    assert signal.source_names == ["Example News", "Example Blog"]
    assert 0.0 < signal.media_score < 1.0
    assert len(provider.calls) == 1
    assert provider.calls[0]["keywords"] == ["graph", "agent"]


def test_high_quality_media_source_weighting() -> None:
    normal_service, _ = make_service(
        [
            {"source_name": "Example Blog", "published_at": NOW - timedelta(days=1)},
            {"source_name": "Another Blog", "published_at": NOW - timedelta(days=1)},
        ]
    )
    quality_service, _ = make_service(
        [
            {"source_name": "Nature News", "published_at": NOW - timedelta(days=1)},
            {"source_name": "MIT Technology Review", "published_at": NOW - timedelta(days=1)},
        ]
    )

    normal_signal = normal_service.get_signal("Paper title")
    quality_signal = quality_service.get_signal("Paper title")

    assert quality_signal.high_quality_mention_count == 2
    assert quality_signal.media_score > normal_signal.media_score


def test_recent_mentions_score_higher_when_dates_are_provided() -> None:
    recent_service, _ = make_service(
        [
            {"source_name": "Example News", "published_at": NOW - timedelta(days=1)},
            {"source_name": "Example News 2", "published_at": NOW - timedelta(days=2)},
        ]
    )
    old_service, _ = make_service(
        [
            {"source_name": "Example News", "published_at": NOW - timedelta(days=80)},
            {"source_name": "Example News 2", "published_at": NOW - timedelta(days=90)},
        ]
    )

    assert recent_service.get_signal("Paper").media_score > old_service.get_signal("Paper").media_score


def test_empty_media_mentions_return_zero_signal() -> None:
    service, _ = make_service([])

    signal = service.get_signal(title="Uncovered paper")

    assert signal.mention_count == 0
    assert signal.high_quality_mention_count == 0
    assert signal.source_names == []
    assert signal.media_score == 0.0
    assert signal.mentions == []


def test_media_signal_deduplicates_source_names() -> None:
    service, _ = make_service(
        [
            {"source_name": "Nature News", "published_at": NOW},
            {"source_name": "Nature News", "published_at": NOW},
            {"publisher": {"name": "Science"}, "date": NOW.date()},
        ]
    )

    signal = service.get_signal(title="Paper")

    assert signal.source_names == ["Nature News", "Science"]
    assert signal.high_quality_mention_count == 3
