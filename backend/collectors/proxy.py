from __future__ import annotations

from typing import Any

from backend.collectors.base import CollectorConfig


class CollectorProxyConfig:
    """Resolve explicit collector proxy settings for HTTP clients."""

    def __init__(self, config: CollectorConfig) -> None:
        self.proxy = self._clean(config.proxy)
        self.http_proxy = self._clean(config.http_proxy)
        self.https_proxy = self._clean(config.https_proxy)

    @property
    def is_configured(self) -> bool:
        """Return whether any explicit collector proxy is configured."""
        return bool(self.proxy or self.http_proxy or self.https_proxy)

    def httpx_proxy(self) -> str | None:
        """Return the single proxy URL to use for https-first httpx collectors."""
        return self.proxy or self.https_proxy or self.http_proxy

    def httpx_client_kwargs(self) -> dict[str, object]:
        """Return httpx kwargs that preserve default behavior unless a proxy is explicit."""
        proxy = self.httpx_proxy()
        if not proxy:
            return {}
        return {"proxy": proxy, "trust_env": False}

    def requests_proxies(self) -> dict[str, str] | None:
        """Return a requests-compatible proxies mapping."""
        if self.proxy:
            return {"http": self.proxy, "https": self.proxy}

        proxies: dict[str, str] = {}
        if self.http_proxy:
            proxies["http"] = self.http_proxy
        if self.https_proxy:
            proxies["https"] = self.https_proxy
        return proxies or None

    def apply_requests_session(self, session: Any) -> None:
        """Apply explicit proxy settings to a requests-like session if configured."""
        proxies = self.requests_proxies()
        if not proxies:
            return

        session_proxies = getattr(session, "proxies", None)
        if isinstance(session_proxies, dict):
            session_proxies.update(proxies)
            return

        setattr(session, "proxies", proxies)

    @staticmethod
    def _clean(value: str | None) -> str | None:
        normalized = value.strip() if value else ""
        return normalized or None


def collector_proxy_config(config: CollectorConfig) -> CollectorProxyConfig:
    """Build a proxy resolver from shared collector config."""
    return CollectorProxyConfig(config)
