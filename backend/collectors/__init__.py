"""Collector interfaces and source-specific placeholders."""

from backend.collectors.arxiv_collector import ArxivCollector
from backend.collectors.base import BaseCollector, CollectedItem, CollectorConfig, ResearchItem
from backend.collectors.github_collector import GitHubCollector
from backend.collectors.pubmed_collector import PubMedCollector
from backend.collectors.rss_collector import RSSCollector
from backend.collectors.web_collector import WebDiscoveryCollector

__all__ = [
    "ArxivCollector",
    "BaseCollector",
    "CollectedItem",
    "CollectorConfig",
    "GitHubCollector",
    "PubMedCollector",
    "ResearchItem",
    "RSSCollector",
    "WebDiscoveryCollector",
]
