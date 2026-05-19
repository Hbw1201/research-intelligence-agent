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


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
