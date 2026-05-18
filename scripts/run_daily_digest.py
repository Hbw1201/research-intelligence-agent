from __future__ import annotations

import argparse
import asyncio
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
from backend.config import get_settings
from backend.services.daily_pipeline import CollectorProtocol, DailyIntelligencePipeline
from backend.services.digest_service import ChineseDigestService
from backend.services.llm_client import ExternalLLMClient


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
    return parser.parse_args()


def build_collector_config() -> CollectorConfig:
    settings = get_settings()
    delay_seconds = 0.0
    if settings.collector_rate_limit_per_minute > 0:
        delay_seconds = 60.0 / settings.collector_rate_limit_per_minute
    return CollectorConfig(
        max_retries=settings.collector_max_retries,
        rate_limit_delay_seconds=delay_seconds,
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
    return collectors


async def run() -> None:
    args = parse_args()
    keywords = split_csv(args.keywords)
    sources = split_csv(args.sources)
    collectors = build_collectors(sources, args.rss_feed_url)
    digest_service = ChineseDigestService(ExternalLLMClient())
    pipeline = DailyIntelligencePipeline(
        collectors=collectors,
        digest_service=digest_service,
    )

    result = await pipeline.run(
        keywords=keywords,
        user_profile=args.user_profile,
        max_items=args.max_items,
        sources=sources,
        output_path=args.output_path,
    )
    print(result.report)
    if result.output_path:
        print(f"\nSaved report: {result.output_path}")


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


if __name__ == "__main__":
    asyncio.run(run())
