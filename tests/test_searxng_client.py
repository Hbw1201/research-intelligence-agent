from __future__ import annotations

from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.search.searxng_client import SearxNGClient
from backend.search.searxng_errors import SearxNGBlockedEnginesError


class FakeSearchHTTPClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return httpx.Response(
            status_code=200,
            json=self.payload,
            request=httpx.Request("GET", url),
        )


def make_settings() -> Settings:
    return Settings(
        _env_file=None,
        web_search_provider="searxng",
        web_search_base_url="http://localhost:8080",
    )


class SearchCategorySettings:
    web_search_provider = "searxng"
    web_search_base_url = "http://localhost:8080"
    web_search_category = "dataset"


@pytest.mark.anyio
async def test_searxng_client_sends_json_search_params() -> None:
    fake_http = FakeSearchHTTPClient({"results": []})
    client = SearxNGClient(settings=make_settings(), http_client=fake_http)

    results = await client.search("single-cell foundation model", max_results=5)

    assert results == []
    assert fake_http.calls[0]["url"] == "http://localhost:8080/search"
    assert fake_http.calls[0]["params"] == {
        "q": "single-cell foundation model",
        "format": "json",
        "language": "auto",
        "categories": "general",
    }


@pytest.mark.anyio
async def test_searxng_client_falls_back_to_general_for_unsupported_category() -> None:
    fake_http = FakeSearchHTTPClient({"results": []})
    client = SearxNGClient(settings=SearchCategorySettings(), http_client=fake_http)  # type: ignore[arg-type]

    await client.search("single-cell dataset", max_results=5)

    assert fake_http.calls[0]["params"]["categories"] == "general"


@pytest.mark.anyio
async def test_searxng_client_reports_blocked_engines_when_zero_results() -> None:
    fake_http = FakeSearchHTTPClient(
        {
            "results": [],
            "unresponsive_engines": [
                ["brave", "too many requests"],
                ["google", "CAPTCHA"],
            ],
        }
    )
    client = SearxNGClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(SearxNGBlockedEnginesError, match="engines blocked/rate-limited"):
        await client.search("single-cell foundation model", max_results=5)


@pytest.mark.anyio
async def test_searxng_client_parses_mocked_json_response() -> None:
    fake_http = FakeSearchHTTPClient(
        {
            "results": [
                {
                    "title": "Single-cell foundation model",
                    "url": "https://example.com/paper",
                    "content": "A useful update.",
                    "engine": "semantic scholar",
                    "publishedDate": "2026-05-19T08:30:00+00:00",
                    "score": 1.2,
                }
            ]
        }
    )
    client = SearxNGClient(settings=make_settings(), http_client=fake_http)

    results = await client.search("single cell", max_results=10)

    assert len(results) == 1
    result = results[0]
    assert result.title == "Single-cell foundation model"
    assert result.url == "https://example.com/paper"
    assert result.snippet == "A useful update."
    assert result.source == "semantic scholar"
    assert result.published_at is not None
    assert result.metadata["score"] == 1.2
