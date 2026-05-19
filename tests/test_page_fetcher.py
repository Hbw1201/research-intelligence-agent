from __future__ import annotations

from typing import Any

import httpx
import pytest

from backend.collectors.page_fetcher import PageFetcher
from backend.config import Settings


class FakePageHTTPClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **kwargs})
        return self.response


def make_response(
    url: str,
    content: bytes,
    content_type: str,
    status_code: int = 200,
) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=content,
        headers={"content-type": content_type},
        request=httpx.Request("GET", url),
    )


@pytest.mark.anyio
async def test_page_fetcher_skips_binary_content() -> None:
    url = "https://example.com/file.pdf"
    fetcher = PageFetcher(
        settings=Settings(_env_file=None),
        http_client=FakePageHTTPClient(make_response(url, b"%PDF", "application/pdf")),
    )

    result = await fetcher.fetch(url)

    assert result.status == "skipped_content_type"
    assert result.page is None


@pytest.mark.anyio
async def test_page_fetcher_respects_max_bytes() -> None:
    url = "https://example.com/page"
    fetcher = PageFetcher(
        settings=Settings(_env_file=None, web_page_max_bytes=10),
        http_client=FakePageHTTPClient(make_response(url, b"abcdefghijklmnopqrstuvwxyz", "text/plain")),
    )

    result = await fetcher.fetch(url)

    page = result.page
    assert result.status == "fetched"
    assert page is not None
    assert page.content == "abcdefghij"
    assert page.content_type == "text/plain"


@pytest.mark.anyio
async def test_page_fetcher_403_does_not_raise_or_log_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    url = "https://example.com/blocked"
    fetcher = PageFetcher(
        settings=Settings(_env_file=None),
        http_client=FakePageHTTPClient(make_response(url, b"forbidden", "text/html", status_code=403)),
    )

    result = await fetcher.fetch(url)

    assert result.status == "skipped_403"
    assert result.status_code == 403
    assert result.page is None
    assert "Traceback" not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("status_code", [404, 429])
async def test_page_fetcher_expected_http_skips_are_quiet(
    status_code: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    url = f"https://example.com/status/{status_code}"
    fetcher = PageFetcher(
        settings=Settings(_env_file=None),
        http_client=FakePageHTTPClient(make_response(url, b"blocked", "text/html", status_code=status_code)),
    )

    result = await fetcher.fetch(url)

    assert result.status == f"skipped_{status_code}"
    assert "Traceback" not in caplog.text
