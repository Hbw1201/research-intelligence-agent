from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    database_url: str = "postgresql+psycopg://intel:intel@localhost:5432/intel"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "zyai"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model_cheap: str = "glm-5.1"
    llm_model_standard: str = "glm-5.1"
    llm_model_strong: str = "glm-5.1"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 3
    llm_max_tokens: int = 8192
    llm_max_tokens_cheap: int = 4096
    llm_max_tokens_standard: int = 8192
    llm_max_tokens_strong: int = 16384

    wecom_webhook_url: SecretStr | None = None
    wecom_timeout_seconds: float = 10.0
    wecom_max_retries: int = 3
    wecom_markdown_max_bytes: int = 3500
    wecom_proxy: str | None = None
    wecom_http_proxy: str | None = None
    wecom_https_proxy: str | None = None

    collector_max_retries: int = 3
    collector_rate_limit_per_minute: int = 30
    collector_timeout_seconds: float | None = None
    arxiv_timeout_seconds: float | None = None
    collector_proxy: str | None = None
    collector_http_proxy: str | None = None
    collector_https_proxy: str | None = None
    github_token: SecretStr | None = None
    pubmed_email: str | None = None

    web_search_provider: str = "searxng"
    web_search_base_url: str = "http://localhost:8080"
    web_search_api_key: SecretStr | None = None
    web_discovery_max_results: int = 20
    web_discovery_allowed_domains: str | None = None
    web_discovery_blocked_domains: str | None = None
    web_discovery_fetch_pages: bool = False
    web_page_timeout_seconds: float = 30.0
    web_page_max_bytes: int = 2_000_000
    web_discovery_query_expansion: bool = True
    web_discovery_query_categories: str = "general,news,blog,dataset,benchmark,lab,company_research"
    web_discovery_results_per_query: int = 5
    web_discovery_total_max_results: int = 30

    seen_item_store_path: str = "data/seen_items.jsonl"
    filter_seen_items: bool = True
    source_registry_path: str = "data/source_registry.json"
    source_registry_enabled: bool = True
    source_registry_auto_update: bool = False
    report_site_dir: str = "reports/site"
    report_public_base_url: str = ""
    report_push_link_only: bool = False
    report_link_threshold_items: int = 8
    topic_registry_path: str = "data/topic_registry.json"
    hotspot_discovery_enabled: bool = True
    hotspot_max_topics: int = 50
    hotspot_min_score: float = 0.2


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
