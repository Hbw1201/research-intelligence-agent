from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest

from backend.collectors.base import ResearchItem
from backend.collectors.errors import ConciseCollectorError
from backend.services.daily_pipeline import DailyIntelligencePipeline
from backend.services.digest_service import DigestItem
from backend.services.seen_item_store import SeenItemStore


class FakeCollector:
    def __init__(self, name: str, items: list[ResearchItem]) -> None:
        self.name = name
        self.items = items
        self.calls: list[dict[str, Any]] = []

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: object | None = None,
        end_date: object | None = None,
    ) -> list[ResearchItem]:
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        return self.items[:max_results]


class FlakyCollector:
    def __init__(self, name: str, outcomes: list[list[ResearchItem] | Exception]) -> None:
        self.name = name
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def collect(
        self,
        query: str,
        max_results: int,
        start_date: object | None = None,
        end_date: object | None = None,
    ) -> list[ResearchItem]:
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
                "start_date": start_date,
                "end_date": end_date,
            }
        )
        outcome_index = min(len(self.calls) - 1, len(self.outcomes) - 1)
        outcome = self.outcomes[outcome_index]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome[:max_results]


class FakeDigestService:
    def __init__(self) -> None:
        self.summarize_calls: list[dict[str, Any]] = []
        self.format_calls: list[dict[str, Any]] = []

    async def summarize_items(
        self,
        items: list[ResearchItem],
        user_profile: str | None = None,
        max_items: int = 10,
    ) -> list[DigestItem]:
        self.summarize_calls.append(
            {
                "items": items,
                "user_profile": user_profile,
                "max_items": max_items,
            }
        )
        return [
            DigestItem(
                title=item.title,
                item_type=item.item_type,
                source_name=item.source_name,
                url=item.url,
                one_sentence_summary=f"Summary for {item.title}",
                key_points=[f"Point for {item.title}"],
                relevance_reason="Matches the requested topic.",
                recommended_action="Read the item.",
                importance_level="medium",
            )
            for item in items[:max_items]
        ]

    def format_daily_digest(self, digests: list[DigestItem], title: str = "Daily Research Intelligence") -> str:
        self.format_calls.append({"digests": digests, "title": title})
        lines = [f"# {title}", f"count={len(digests)}"]
        lines.extend(f"- {digest.title}: {digest.one_sentence_summary}" for digest in digests)
        return "\n".join(lines)


def make_item(
    title: str,
    url: str,
    external_id: str | None,
    abstract: str = "A graph retrieval paper for multi-agent systems.",
    source_name: str = "arxiv",
) -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract=abstract,
        url=url,
        source_name=source_name,
        source_type="paper",
        item_type="paper",
        authors=["Ada Lovelace"],
        published_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        raw_text=abstract,
        external_id=external_id,
        keywords=[],
        metadata={},
    )


def make_pipeline(collectors: dict[str, FakeCollector], digest_service: FakeDigestService | None = None) -> DailyIntelligencePipeline:
    return DailyIntelligencePipeline(
        collectors=collectors,
        digest_service=digest_service or FakeDigestService(),
        failed_source_retry_delay_seconds=0,
    )


@pytest.mark.anyio
async def test_pipeline_deduplicates_by_url() -> None:
    duplicate_a = make_item("First copy", "https://example.com/paper", "a")
    duplicate_b = make_item("Second copy", "https://example.com/paper/", "b")
    digest_service = FakeDigestService()
    pipeline = make_pipeline(
        {
            "arxiv": FakeCollector("arxiv", [duplicate_a]),
            "pubmed": FakeCollector("pubmed", [duplicate_b]),
        },
        digest_service=digest_service,
    )

    result = await pipeline.run(keywords=["graph"], max_items=10, sources=["arxiv", "pubmed"])

    assert len(result.collected_items) == 2
    assert len(result.unique_items) == 1
    assert result.unique_items[0].title == "First copy"
    assert len(digest_service.summarize_calls[0]["items"]) == 1
    assert "## Deduplication summary" in result.report
    assert "- Collected items: 2" in result.report
    assert "- Duplicates skipped: 1" in result.report
    assert "- New items included: 1" in result.report


@pytest.mark.anyio
async def test_pipeline_deduplicates_by_external_id() -> None:
    first = make_item("First paper", "https://example.com/one", "shared-id")
    duplicate = make_item("Duplicate paper", "https://example.com/two", "shared-id")
    pipeline = make_pipeline(
        {
            "arxiv": FakeCollector("arxiv", [first]),
            "pubmed": FakeCollector("pubmed", [duplicate]),
        }
    )

    result = await pipeline.run(keywords=["agent"], max_items=10, sources=["arxiv", "pubmed"])

    assert len(result.unique_items) == 1
    assert result.unique_items[0].url == "https://example.com/one"


@pytest.mark.anyio
async def test_pipeline_ranking_and_max_items_behavior() -> None:
    matching = make_item(
        "Graph retrieval agent paper",
        "https://example.com/matching",
        "matching",
        abstract="Graph retrieval for multi-agent systems.",
    )
    unrelated = make_item(
        "Unrelated database update",
        "https://example.com/unrelated",
        "unrelated",
        abstract="An operations note without the requested topic.",
        source_name="rss",
    )
    digest_service = FakeDigestService()
    pipeline = make_pipeline({"arxiv": FakeCollector("arxiv", [unrelated, matching])}, digest_service=digest_service)

    result = await pipeline.run(keywords=["graph", "retrieval"], max_items=1, sources=["arxiv"])

    assert len(result.ranked_items) == 1
    assert result.ranked_items[0].item.url == "https://example.com/matching"
    assert len(result.digests) == 1
    assert digest_service.summarize_calls[0]["max_items"] == 1


@pytest.mark.anyio
async def test_pipeline_report_formatting() -> None:
    digest_service = FakeDigestService()
    pipeline = make_pipeline(
        {"arxiv": FakeCollector("arxiv", [make_item("Graph paper", "https://example.com/graph", "graph")])},
        digest_service=digest_service,
    )

    result = await pipeline.run(keywords=["graph", "agent"], user_profile="graph agents", max_items=5, sources=["arxiv"])

    assert result.report.startswith("# Daily Research Intelligence - graph, agent")
    assert "count=1" in result.report
    assert "- Graph paper: Summary for Graph paper" in result.report
    assert digest_service.format_calls[0]["title"] == "Daily Research Intelligence - graph, agent"
    assert digest_service.summarize_calls[0]["user_profile"] == "graph agents"


@pytest.mark.anyio
async def test_pipeline_with_mocked_collectors_and_digest_service() -> None:
    arxiv = FakeCollector("arxiv", [make_item("Arxiv paper", "https://example.com/arxiv", "arxiv")])
    github = FakeCollector(
        "github",
        [
            ResearchItem(
                title="owner/repo",
                abstract="A graph retrieval repository.",
                url="https://github.com/owner/repo",
                source_name="github",
                source_type="code",
                item_type="repository",
                authors=["owner"],
                published_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
                raw_text="A graph retrieval repository.",
                external_id="repo-id",
                keywords=["Python"],
                metadata={"stars": 10},
            )
        ],
    )
    digest_service = FakeDigestService()
    pipeline = make_pipeline({"arxiv": arxiv, "github": github}, digest_service=digest_service)

    result = await pipeline.run(
        keywords=["graph"],
        user_profile=None,
        max_items=2,
        sources=["arxiv", "github"],
    )

    assert len(arxiv.calls) == 1
    assert len(github.calls) == 1
    assert arxiv.calls[0]["query"] == "graph"
    assert github.calls[0]["max_results"] >= 2
    assert len(result.digests) == 2
    assert "Arxiv paper" in result.report
    assert "owner/repo" in result.report


@pytest.mark.anyio
async def test_pipeline_saves_report_to_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "daily.md"
    pipeline = make_pipeline(
        {"arxiv": FakeCollector("arxiv", [make_item("Saved paper", "https://example.com/saved", "saved")])}
    )

    result = await pipeline.run(keywords=["saved"], max_items=1, sources=["arxiv"], output_path=output_path)

    assert result.output_path == output_path
    assert output_path.read_text(encoding="utf-8") == result.report


@pytest.mark.anyio
async def test_pipeline_continues_when_one_collector_fails_but_another_succeeds() -> None:
    arxiv = FakeCollector("arxiv", [make_item("Working paper", "https://example.com/working", "working")])
    pubmed = FlakyCollector("pubmed", [TimeoutError("source timed out")])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": arxiv, "pubmed": pubmed},
        digest_service=FakeDigestService(),
        max_failed_source_retries=0,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["graph"], max_items=5, sources=["pubmed", "arxiv"])

    assert len(result.digests) == 1
    assert result.collector_errors == {"pubmed": "timeout"}
    assert "Working paper" in result.report
    assert "Collector warnings" in result.report


@pytest.mark.anyio
async def test_failed_collector_succeeds_during_deferred_retry() -> None:
    item = make_item("Retry paper", "https://example.com/retry", "retry")
    arxiv = FlakyCollector("arxiv", [TimeoutError("temporary timeout"), [item]])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": arxiv},
        digest_service=FakeDigestService(),
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["retry"], max_items=5, sources=["arxiv"])

    assert len(arxiv.calls) == 2
    assert result.collector_errors == {}
    assert result.collected_items == [item]
    assert "Collector warnings" not in result.report


@pytest.mark.anyio
async def test_failed_collector_still_fails_after_five_retries_and_records_error() -> None:
    working = FakeCollector("arxiv", [make_item("Working paper", "https://example.com/ok", "ok")])
    failing = FlakyCollector("pubmed", [TimeoutError("still slow")])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": working, "pubmed": failing},
        digest_service=FakeDigestService(),
        max_failed_source_retries=5,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["graph"], max_items=5, sources=["arxiv", "pubmed"])

    assert len(failing.calls) == 6
    assert result.collector_errors == {"pubmed": "timeout"}
    assert "## Collector warnings" in result.report
    assert "- pubmed: timeout" in result.report


@pytest.mark.anyio
async def test_all_collectors_fail_raises_clear_runtime_error() -> None:
    arxiv = FlakyCollector("arxiv", [TimeoutError("arxiv slow")])
    pubmed = FlakyCollector("pubmed", [RuntimeError("pubmed unavailable")])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": arxiv, "pubmed": pubmed},
        digest_service=FakeDigestService(),
        max_failed_source_retries=1,
        failed_source_retry_delay_seconds=0,
    )

    with pytest.raises(RuntimeError, match="All selected collectors failed: arxiv, pubmed"):
        await pipeline.run(keywords=["graph"], max_items=5, sources=["arxiv", "pubmed"])


@pytest.mark.anyio
async def test_collector_warnings_appear_in_markdown_report() -> None:
    arxiv = FakeCollector("arxiv", [make_item("Warning paper", "https://example.com/warning", "warning")])
    github = FlakyCollector("github", [RuntimeError("rate limited")])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": arxiv, "github": github},
        digest_service=FakeDigestService(),
        max_failed_source_retries=1,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["graph"], max_items=5, sources=["arxiv", "github"])

    assert "## Collector warnings" in result.report
    assert "- github: RuntimeError: rate limited" in result.report


@pytest.mark.anyio
async def test_pubmed_timeout_and_github_success_still_produces_report() -> None:
    github = FakeCollector(
        "github",
        [make_item("GitHub repo", "https://github.com/example/repo", "repo", source_name="github")],
    )
    pubmed = FlakyCollector("pubmed", [httpx.ConnectTimeout("connect timed out")])
    pipeline = DailyIntelligencePipeline(
        collectors={"pubmed": pubmed, "github": github},
        digest_service=FakeDigestService(),
        max_failed_source_retries=0,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["single-cell"], max_items=5, sources=["pubmed", "github"])

    assert len(result.digests) == 1
    assert "GitHub repo" in result.report
    assert result.collector_errors == {"pubmed": "ConnectTimeout: connect timed out"}
    assert "Traceback" not in result.report


@pytest.mark.anyio
async def test_arxiv_429_and_github_success_still_produces_report() -> None:
    github = FakeCollector(
        "github",
        [make_item("GitHub repo", "https://github.com/example/repo", "repo", source_name="github")],
    )
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("GET", "https://export.arxiv.org/api/query"),
    )
    arxiv = FlakyCollector("arxiv", [httpx.HTTPStatusError("too many requests", request=response.request, response=response)])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": arxiv, "github": github},
        digest_service=FakeDigestService(),
        max_failed_source_retries=5,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["single-cell"], max_items=5, sources=["arxiv", "github"])

    assert len(arxiv.calls) == 1
    assert len(result.digests) == 1
    assert "GitHub repo" in result.report
    assert result.collector_errors == {"arxiv": "HTTP 429"}
    assert "- arxiv: HTTP 429" in result.report


@pytest.mark.anyio
async def test_collector_warnings_are_concise_without_traceback() -> None:
    response = httpx.Response(
        status_code=429,
        request=httpx.Request("GET", "https://example.com"),
    )
    failing = FlakyCollector("arxiv", [httpx.HTTPStatusError("raw verbose provider message", request=response.request, response=response)])
    working = FakeCollector("github", [make_item("Working repo", "https://github.com/example/repo", "repo")])
    pipeline = DailyIntelligencePipeline(
        collectors={"arxiv": failing, "github": working},
        digest_service=FakeDigestService(),
        max_failed_source_retries=1,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["graph"], max_items=5, sources=["arxiv", "github"])

    assert result.collector_errors == {"arxiv": "HTTP 429"}
    assert "Traceback" not in result.report
    assert "raw verbose provider message" not in result.report


@pytest.mark.anyio
async def test_web_http_400_warning_is_concise_without_traceback() -> None:
    failing = FlakyCollector(
        "web",
        [ConciseCollectorError("SearxNG query failed with HTTP 400 for one expanded query")],
    )
    working = FakeCollector("github", [make_item("Working repo", "https://github.com/example/repo", "repo")])
    pipeline = DailyIntelligencePipeline(
        collectors={"web": failing, "github": working},
        digest_service=FakeDigestService(),
        max_failed_source_retries=1,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["single-cell"], max_items=5, sources=["web", "github"])

    assert result.collector_errors == {"web": "SearxNG query failed with HTTP 400 for one expanded query"}
    assert "- web: SearxNG query failed with HTTP 400 for one expanded query" in result.report
    assert "Traceback" not in result.report


@pytest.mark.anyio
async def test_web_blocked_engines_warning_is_concise_without_traceback() -> None:
    failing = FlakyCollector(
        "web",
        [ConciseCollectorError("SearxNG returned zero results; engines blocked/rate-limited")],
    )
    working = FakeCollector("github", [make_item("Working repo", "https://github.com/example/repo", "repo")])
    pipeline = DailyIntelligencePipeline(
        collectors={"web": failing, "github": working},
        digest_service=FakeDigestService(),
        max_failed_source_retries=1,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["single-cell"], max_items=5, sources=["web", "github"])

    assert result.collector_errors == {"web": "SearxNG returned zero results; engines blocked/rate-limited"}
    assert "- web: SearxNG returned zero results; engines blocked/rate-limited" in result.report
    assert "Traceback" not in result.report


def test_pipeline_deduplicates_web_urls_after_removing_tracking_params() -> None:
    first = make_item(
        "First web result",
        "https://example.com/page?utm_source=newsletter&x=1&fbclid=abc",
        None,
        source_name="web",
    )
    duplicate = make_item(
        "Duplicate web result",
        "https://example.com/page/?x=1&utm_medium=social",
        None,
        source_name="web",
    )

    unique_items = DailyIntelligencePipeline.deduplicate_items([first, duplicate])

    assert len(unique_items) == 1
    assert unique_items[0].title == "First web result"


@pytest.mark.anyio
async def test_pipeline_skips_same_url_on_second_run(tmp_path: Path) -> None:
    item = make_item("Seen paper", "https://example.com/seen?utm_source=lab", "seen")
    digest_service = FakeDigestService()
    store = SeenItemStore(tmp_path / "seen_items.jsonl")
    pipeline = DailyIntelligencePipeline(
        collectors={"web": FakeCollector("web", [item])},
        digest_service=digest_service,
        seen_item_store=store,
        failed_source_retry_delay_seconds=0,
    )

    first = await pipeline.run(keywords=["graph"], max_items=5, sources=["web"])
    store.mark_seen(first.included_items, pushed=True)
    second = await pipeline.run(keywords=["graph"], max_items=5, sources=["web"])

    assert len(first.included_items) == 1
    assert second.included_items == []
    assert second.ranked_items == []
    assert second.digests == []
    assert second.deduplication_summary.collected_items == 1
    assert second.deduplication_summary.duplicates_skipped == 1
    assert second.deduplication_summary.new_items_included == 0
    assert "No new items after deduplication." in second.report
    assert len(digest_service.summarize_calls) == 1


@pytest.mark.anyio
async def test_pipeline_include_seen_keeps_old_items(tmp_path: Path) -> None:
    item = make_item("Old paper", "https://example.com/old?utm_campaign=lab", "old")
    digest_service = FakeDigestService()
    store = SeenItemStore(tmp_path / "seen_items.jsonl")
    store.mark_seen([item], pushed=True)
    pipeline = DailyIntelligencePipeline(
        collectors={"web": FakeCollector("web", [item])},
        digest_service=digest_service,
        seen_item_store=store,
        failed_source_retry_delay_seconds=0,
    )

    result = await pipeline.run(keywords=["graph"], max_items=5, sources=["web"], include_seen_items=True)

    assert len(result.included_items) == 1
    assert result.included_items[0].title == "Old paper"
    assert result.deduplication_summary.duplicates_skipped == 0
    assert result.deduplication_summary.new_items_included == 1
    assert len(digest_service.summarize_calls) == 1
