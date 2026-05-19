from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.collectors.arxiv_collector import ArxivCollector
from backend.collectors.base import CollectorConfig
from backend.collectors.github_collector import GitHubCollector
from backend.collectors.pubmed_collector import PubMedCollector
from backend.collectors.rss_collector import RSSCollector
from backend.collectors.web_collector import WebDiscoveryCollector
from backend.config import get_settings
from backend.search.searxng_client import SearxNGClient
from backend.services.daily_pipeline import CollectorProtocol, DailyIntelligencePipeline
from backend.services.digest_service import ChineseDigestService
from backend.services.html_report_renderer import HtmlReportMetadata, HtmlReportRenderer
from backend.services.llm_client import ExternalLLMClient
from backend.services.report_site import ReportSiteResult, ReportSiteWriter
from backend.services.seen_item_store import SeenItemStore
from backend.services.source_registry import SourceRegistry
from backend.services.topic_registry import HotspotDiscoveryService, TopicRegistry
from backend.services.wecom import PushMessage, WeComPushService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the manual daily research intelligence digest.")
    parser.add_argument(
        "--keywords",
        required=True,
        help="Comma-separated topic keywords, for example: multi-agent systems,RAG",
    )
    parser.add_argument("--user-profile", default=None, help="Optional free-text user or group research profile.")
    parser.add_argument("--max-items", type=int, default=10, help="Maximum ranked items to include in the digest.")
    parser.add_argument(
        "--sources",
        default="arxiv,pubmed,github",
        help="Comma-separated sources to collect from: arxiv,pubmed,github,rss",
    )
    parser.add_argument(
        "--rss-feed-url",
        action="append",
        default=[],
        help="RSS/Atom feed URL. Required when --sources includes rss. May be passed multiple times.",
    )
    parser.add_argument(
        "--output-path",
        default=None,
        help="Optional output path. Relative paths are saved under reports/.",
    )
    parser.add_argument("--push-wecom", action="store_true", help="Push the generated report to WeCom.")
    parser.add_argument("--wecom-title", default="今日科研情报", help="Title used for the WeCom push message.")
    parser.add_argument(
        "--seen-store-path",
        default=None,
        help="JSONL path used to remember items across digest runs.",
    )
    parser.add_argument("--include-seen", action="store_true", help="Include items already present in the seen-item store.")
    parser.add_argument(
        "--mark-seen",
        action="store_true",
        help="Mark included items as seen after report generation succeeds.",
    )
    parser.add_argument(
        "--update-source-registry",
        action="store_true",
        help="Register useful discovered web/RSS source candidates after collection.",
    )
    parser.add_argument("--html-report", action="store_true", help="Generate a static HTML report under REPORT_SITE_DIR.")
    parser.add_argument(
        "--push-link-only",
        action="store_true",
        help="When pushing WeCom, send only a short summary and the latest HTML report link.",
    )
    return parser.parse_args()


def build_collector_config() -> CollectorConfig:
    settings = get_settings()
    delay_seconds = 0.0
    if settings.collector_rate_limit_per_minute > 0:
        delay_seconds = 60.0 / settings.collector_rate_limit_per_minute
    return CollectorConfig(
        max_retries=settings.collector_max_retries,
        rate_limit_delay_seconds=delay_seconds,
        collector_timeout_seconds=settings.collector_timeout_seconds,
        arxiv_timeout_seconds=settings.arxiv_timeout_seconds,
        proxy=settings.collector_proxy,
        http_proxy=settings.collector_http_proxy,
        https_proxy=settings.collector_https_proxy,
    )


def build_collectors(sources: list[str], rss_feed_urls: list[str]) -> dict[str, CollectorProtocol]:
    settings = get_settings()
    config = build_collector_config()
    token = settings.github_token.get_secret_value() if settings.github_token else None

    collectors: dict[str, CollectorProtocol] = {}
    if "arxiv" in sources:
        collectors["arxiv"] = ArxivCollector(config=config)
    if "pubmed" in sources:
        collectors["pubmed"] = PubMedCollector(config=config)
    if "github" in sources:
        collectors["github"] = GitHubCollector(config=config, token=token)
    if "rss" in sources:
        if not rss_feed_urls:
            raise ValueError("--rss-feed-url is required when --sources includes rss.")
        collectors["rss"] = RSSCollector(feed_url=rss_feed_urls[0], config=config)
    if "web" in sources:
        if settings.web_search_provider.strip().lower() != "searxng":
            raise ValueError("Only WEB_SEARCH_PROVIDER=searxng is supported for MVP web discovery.")
        collectors["web"] = WebDiscoveryCollector(
            search_client=SearxNGClient(settings=settings, config=config),
            settings=settings,
            config=config,
        )
    return collectors


async def run() -> None:
    args = parse_args()
    settings = get_settings()
    keywords = split_csv(args.keywords)
    sources = split_csv(args.sources)
    collectors = build_collectors(sources, getattr(args, "rss_feed_url", []))
    digest_service = ChineseDigestService(ExternalLLMClient())
    seen_store_path = getattr(args, "seen_store_path", None) or settings.seen_item_store_path
    seen_item_store = SeenItemStore(seen_store_path)
    update_source_registry = (
        settings.source_registry_enabled
        and (getattr(args, "update_source_registry", False) or settings.source_registry_auto_update)
    )
    source_registry = SourceRegistry(settings.source_registry_path) if update_source_registry else None
    hotspot_discovery = (
        HotspotDiscoveryService(
            topic_registry=TopicRegistry(settings.topic_registry_path),
            max_topics=settings.hotspot_max_topics,
            min_score=settings.hotspot_min_score,
        )
        if settings.hotspot_discovery_enabled
        else None
    )
    pipeline = DailyIntelligencePipeline(
        collectors=collectors,
        digest_service=digest_service,
        seen_item_store=seen_item_store,
        source_registry=source_registry,
        hotspot_discovery_service=hotspot_discovery,
    )
    include_seen_items = getattr(args, "include_seen", False) or not settings.filter_seen_items

    result = await pipeline.run(
        keywords=keywords,
        user_profile=args.user_profile,
        max_items=args.max_items,
        sources=sources,
        output_path=args.output_path,
        include_seen_items=include_seen_items,
        update_source_registry=update_source_registry,
        update_hotspots=settings.hotspot_discovery_enabled,
    )
    print(result.report)
    if result.output_path:
        print(f"\nSaved report: {result.output_path}")
    html_result: ReportSiteResult | None = None
    should_generate_html = getattr(args, "html_report", False) or _should_push_link_only(args, settings, result)
    if should_generate_html:
        html_result = _write_html_report(
            title=_report_title(keywords),
            result=result,
            keywords=keywords,
            sources=sources,
            settings=settings,
        )
        print(f"\nSaved HTML report: {html_result.report_path}")
        print(f"Latest HTML report: {html_result.latest_path}")
        if html_result.latest_public_url:
            print(f"Public report URL: {html_result.latest_public_url}")
        else:
            print("No public report URL configured. Set REPORT_PUBLIC_BASE_URL to share the HTML report link.")
    included_items = getattr(result, "included_items", None)
    if included_items:
        seen_item_store.mark_seen(included_items, pushed=False)
        if getattr(args, "mark_seen", False):
            print(f"\nMarked {len(included_items)} items as seen.")
    if args.push_wecom:
        if included_items == [] and not getattr(args, "include_seen", False):
            print("\nSkipped WeCom push: No new items after deduplication.")
            return
        push_link_only = _should_push_link_only(args, settings, result)
        if push_link_only:
            if html_result is None:
                html_result = _write_html_report(
                    title=_report_title(keywords),
                    result=result,
                    keywords=keywords,
                    sources=sources,
                    settings=settings,
                )
                print(f"\nSaved HTML report: {html_result.report_path}")
            if not html_result.latest_public_url:
                print("Skipped WeCom push-link-only: REPORT_PUBLIC_BASE_URL is not configured.")
                print(f"Local HTML report: {html_result.latest_path}")
                return
            markdown = build_link_only_wecom_message(
                count=len(getattr(result, "digests", []) or []),
                titles=[digest.title for digest in (getattr(result, "digests", []) or [])],
                report_url=html_result.latest_public_url,
            )
        else:
            markdown = result.report
        await WeComPushService().send_markdown(PushMessage(title=args.wecom_title, markdown=markdown))
        if included_items:
            seen_item_store.mark_seen(included_items, pushed=True)
        print("\nPushed WeCom report link." if push_link_only else "\nPushed WeCom markdown digest.")


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def build_link_only_wecom_message(count: int, titles: list[str], report_url: str) -> str:
    lines = ["今日科研情报已更新", f"共 {count} 条"]
    top_titles = [title.strip() for title in titles if title.strip()][:3]
    if top_titles:
        lines.append("")
        lines.extend(f"- {title}" for title in top_titles)
    lines.extend(["", f"阅读全文：{report_url}"])
    return "\n".join(lines)


def _should_push_link_only(args: argparse.Namespace, settings: object, result: object) -> bool:
    if not getattr(args, "push_wecom", False):
        return False
    if getattr(args, "push_link_only", False):
        return True
    if not getattr(settings, "report_push_link_only", False):
        return False
    threshold = max(0, int(getattr(settings, "report_link_threshold_items", 0)))
    digest_count = len(getattr(result, "digests", []) or [])
    return threshold == 0 or digest_count >= threshold


def _write_html_report(
    title: str,
    result: object,
    keywords: list[str],
    sources: list[str],
    settings: object,
) -> ReportSiteResult:
    generated_at = getattr(settings, "_report_generated_at", None)
    metadata = HtmlReportMetadata(
        generated_at=generated_at if generated_at is not None else datetime.now(timezone.utc),
        sources=sources,
        keywords=keywords,
        warnings=[f"{source}: {error}" for source, error in sorted((getattr(result, "collector_errors", {}) or {}).items())],
        dedup_summary=_dedup_summary_dict(getattr(result, "deduplication_summary", None)),
    )
    html_report = HtmlReportRenderer().render(
        title=title,
        markdown_report=getattr(result, "report", ""),
        digests=getattr(result, "digests", []) or [],
        items=getattr(result, "included_items", []) or [],
        metadata=metadata,
    )
    return ReportSiteWriter(
        site_dir=getattr(settings, "report_site_dir", "reports/site"),
        public_base_url=getattr(settings, "report_public_base_url", ""),
    ).save(html_report, generated_at=metadata.generated_at)


def _dedup_summary_dict(summary: object | None) -> dict[str, int] | None:
    if summary is None:
        return None
    return {
        "collected_items": int(getattr(summary, "collected_items", 0)),
        "duplicates_skipped": int(getattr(summary, "duplicates_skipped", 0)),
        "new_items_included": int(getattr(summary, "new_items_included", 0)),
    }


def _report_title(keywords: list[str]) -> str:
    topic = ", ".join(keywords)
    return f"Daily Research Intelligence - {topic}" if topic else "Daily Research Intelligence"


if __name__ == "__main__":
    asyncio.run(run())
