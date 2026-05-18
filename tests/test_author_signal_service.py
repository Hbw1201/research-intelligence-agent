from typing import Any

from backend.services.author_signal_service import (
    AuthorSignalService,
    to_ranking_external_signals,
)
from backend.services.media_signal_service import MediaSignal


class FakeAuthorMetricsProvider:
    def __init__(self, metrics: dict[str, dict[str, Any]]) -> None:
        self.metrics = metrics
        self.calls: list[dict[str, Any]] = []

    def get_author_metrics(
        self,
        title: str | None,
        authors: list[str],
        external_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        self.calls.append(
            {
                "title": title,
                "authors": authors,
                "external_id": external_id,
                "metadata": metadata,
            }
        )
        return self.metrics


def test_first_last_and_corresponding_author_fallback_extraction() -> None:
    service = AuthorSignalService()

    signal = service.get_signal(
        title="Test paper",
        authors=["Ada Lovelace", "Alan Turing", "Grace Hopper"],
        external_id="paper-1",
        metadata={},
    )

    assert signal.first_author == "Ada Lovelace"
    assert signal.senior_author == "Grace Hopper"
    assert signal.corresponding_author == "Grace Hopper"


def test_corresponding_author_metadata_if_available() -> None:
    service = AuthorSignalService()

    signal = service.get_signal(
        title="Test paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        external_id=None,
        metadata={"corresponding_author": "Alan Turing"},
    )

    assert signal.first_author == "Ada Lovelace"
    assert signal.senior_author == "Grace Hopper"
    assert signal.corresponding_author == "Alan Turing"


def test_author_score_normalization_from_mocked_metrics() -> None:
    provider = FakeAuthorMetricsProvider(
        {
            "Ada Lovelace": {"citations": 100, "h_index": 8},
            "Grace Hopper": {"citations": 1000000, "h_index": 200},
        }
    )
    service = AuthorSignalService(provider=provider)

    signal = service.get_signal(
        title="Important paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        external_id="paper-2",
        metadata={"source": "test"},
    )

    assert signal.first_author_citations == 100
    assert signal.senior_author_citations == 1000000
    assert signal.first_author_h_index == 8
    assert signal.senior_author_h_index == 200
    assert 0.0 <= signal.author_score <= 1.0
    assert signal.author_score > 0.5
    assert len(provider.calls) == 1


def test_metadata_author_metrics_provider_is_deterministic() -> None:
    service = AuthorSignalService()

    signal = service.get_signal(
        title=None,
        authors=["Ada Lovelace", "Grace Hopper"],
        external_id=None,
        metadata={
            "author_metrics": {
                "Ada Lovelace": {"citation_count": "1,200", "hIndex": "12"},
                "Grace Hopper": {"total_citations": 5000, "hindex": 33},
            }
        },
    )

    assert signal.first_author_citations == 1200
    assert signal.senior_author_citations == 5000
    assert signal.first_author_h_index == 12
    assert signal.senior_author_h_index == 33
    assert signal.author_score > 0


def test_conversion_to_ranking_external_signals() -> None:
    author_signal = AuthorSignalService(
        provider=FakeAuthorMetricsProvider(
            {
                "Ada Lovelace": {"citations": 1000, "h_index": 20},
                "Grace Hopper": {"citations": 3000, "h_index": 40},
            }
        )
    ).get_signal(
        title="Test paper",
        authors=["Ada Lovelace", "Grace Hopper"],
        external_id=None,
        metadata=None,
    )
    media_signal = MediaSignal(
        mention_count=2,
        high_quality_mention_count=1,
        source_names=["Nature News", "Example Blog"],
        media_score=0.75,
        mentions=[{"source_name": "Nature News"}, {"source_name": "Example Blog"}],
    )

    signals = to_ranking_external_signals(author_signal=author_signal, media_signal=media_signal)

    assert signals.author_score == author_signal.author_score
    assert signals.media_score == 0.75
    assert signals.author_metrics == author_signal.raw_metrics
    assert signals.media_mentions == media_signal.mentions
