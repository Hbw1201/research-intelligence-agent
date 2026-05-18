from types import SimpleNamespace

from backend.collectors.base import CollectorConfig
from backend.collectors.proxy import collector_proxy_config


def test_proxy_helper_returns_httpx_proxy_when_collector_proxy_is_set() -> None:
    proxy = collector_proxy_config(
        CollectorConfig(
            proxy=" http://127.0.0.1:7897 ",
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    assert proxy.httpx_client_kwargs() == {
        "proxy": "http://127.0.0.1:7897",
        "trust_env": False,
    }


def test_proxy_helper_returns_requests_proxies_when_collector_proxy_is_set() -> None:
    proxy = collector_proxy_config(
        CollectorConfig(
            proxy="http://127.0.0.1:7897",
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    assert proxy.requests_proxies() == {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }


def test_proxy_helper_uses_separate_http_and_https_proxies() -> None:
    proxy = collector_proxy_config(
        CollectorConfig(
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    assert proxy.httpx_client_kwargs() == {
        "proxy": "http://127.0.0.1:7899",
        "trust_env": False,
    }
    assert proxy.requests_proxies() == {
        "http": "http://127.0.0.1:7898",
        "https": "http://127.0.0.1:7899",
    }


def test_proxy_helper_preserves_existing_behavior_when_no_proxy_is_set() -> None:
    proxy = collector_proxy_config(CollectorConfig())

    assert proxy.httpx_client_kwargs() == {}
    assert proxy.requests_proxies() is None


def test_proxy_helper_applies_requests_session_proxies_when_configured() -> None:
    proxy = collector_proxy_config(CollectorConfig(proxy="http://127.0.0.1:7897"))
    session = SimpleNamespace(proxies={})

    proxy.apply_requests_session(session)

    assert session.proxies == {
        "http": "http://127.0.0.1:7897",
        "https": "http://127.0.0.1:7897",
    }
