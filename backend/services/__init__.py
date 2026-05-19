"""Service layer placeholders."""

from backend.services.author_signal_service import (
    AuthorMetricsProvider,
    AuthorSignal,
    AuthorSignalService,
    MetadataAuthorMetricsProvider,
    to_ranking_external_signals,
)
from backend.services.daily_pipeline import (
    CollectorProtocol,
    CollectorRunResult,
    DailyIntelligencePipeline,
    DailyPipelineOptions,
    DailyPipelineResult,
    DeduplicationSummary,
    DigestServiceProtocol,
)
from backend.services.digest_service import ChineseDigestService, DigestItem
from backend.services.feedback import FeedbackService
from backend.services.html_report_renderer import HtmlReportMetadata, HtmlReportRenderer
from backend.services.llm_client import (
    ExternalLLMClient,
    InvalidLLMResponseError,
    LLMClientError,
    LLMRequest,
    MissingLLMConfigError,
    TruncatedLLMResponseError,
)
from backend.services.ranking_service import (
    RankingConfig,
    RankingExternalSignals,
    RankedItem,
    RelevanceRanker,
    RelevanceRankingService,
)
from backend.services.report_site import ReportSiteResult, ReportSiteWriter
from backend.services.seen_item_store import SeenItemStore
from backend.services.source_registry import SourceRecord, SourceRegistry, SourceRegistryUpdateSummary
from backend.services.topic_registry import HotspotDiscoveryService, TopicRecord, TopicRegistry
from backend.services.media_signal_service import (
    EmptyMediaMentionsProvider,
    MediaMentionsProvider,
    MediaSignal,
    MediaSignalService,
)
from backend.services.wecom import PushMessage, WeComPushService

__all__ = [
    "AuthorMetricsProvider",
    "AuthorSignal",
    "AuthorSignalService",
    "ChineseDigestService",
    "CollectorProtocol",
    "CollectorRunResult",
    "DailyIntelligencePipeline",
    "DailyPipelineOptions",
    "DailyPipelineResult",
    "DeduplicationSummary",
    "DigestItem",
    "DigestServiceProtocol",
    "EmptyMediaMentionsProvider",
    "ExternalLLMClient",
    "InvalidLLMResponseError",
    "LLMClientError",
    "FeedbackService",
    "HtmlReportMetadata",
    "HtmlReportRenderer",
    "HotspotDiscoveryService",
    "LLMRequest",
    "MediaMentionsProvider",
    "MediaSignal",
    "MediaSignalService",
    "MetadataAuthorMetricsProvider",
    "MissingLLMConfigError",
    "PushMessage",
    "RankingConfig",
    "RankingExternalSignals",
    "RankedItem",
    "RelevanceRanker",
    "RelevanceRankingService",
    "ReportSiteResult",
    "ReportSiteWriter",
    "SeenItemStore",
    "SourceRecord",
    "SourceRegistry",
    "SourceRegistryUpdateSummary",
    "TopicRecord",
    "TopicRegistry",
    "to_ranking_external_signals",
    "TruncatedLLMResponseError",
    "WeComPushService",
]
