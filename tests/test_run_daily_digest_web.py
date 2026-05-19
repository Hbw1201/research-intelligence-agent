from __future__ import annotations

from typing import Any

from backend.config import get_settings
from scripts import run_daily_digest


class FakeSearxNGClient:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


def test_run_daily_digest_build_collectors_accepts_web_without_rss_feed_url(
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("WEB_SEARCH_PROVIDER", "searxng")
    monkeypatch.setenv("WEB_SEARCH_BASE_URL", "http://localhost:8080")
    get_settings.cache_clear()
    monkeypatch.setattr(run_daily_digest, "SearxNGClient", FakeSearxNGClient)

    try:
        collectors = run_daily_digest.build_collectors(["web"], rss_feed_urls=[])
    finally:
        get_settings.cache_clear()

    assert list(collectors) == ["web"]
    assert collectors["web"].name == "web"
