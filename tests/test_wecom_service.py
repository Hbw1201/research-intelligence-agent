from __future__ import annotations

from copy import deepcopy
from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.services.wecom import (
    MissingWeComConfigError,
    PushMessage,
    WeComPushError,
    WeComPushService,
)


class FakeHTTPClient:
    def __init__(self, outcomes: list[httpx.Response | Exception] | None = None) -> None:
        self.outcomes = outcomes or []
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **deepcopy(kwargs)})
        if not self.outcomes:
            return wecom_response({"errcode": 0, "errmsg": "ok"}, url)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_settings(
    webhook_url: str | None = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-secret",
    markdown_max_bytes: int = 1000,
    max_retries: int = 1,
) -> Settings:
    return Settings(
        _env_file=None,
        wecom_webhook_url=webhook_url,
        wecom_timeout_seconds=5,
        wecom_max_retries=max_retries,
        wecom_markdown_max_bytes=markdown_max_bytes,
    )


def wecom_response(payload: dict[str, Any], url: str = "https://example.test/webhook") -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json=payload,
        request=httpx.Request("POST", url),
    )


@pytest.mark.anyio
async def test_send_markdown_splits_long_chinese_content_by_utf8_bytes() -> None:
    max_bytes = 1000
    fake_http = FakeHTTPClient()
    service = WeComPushService(
        settings=make_settings(markdown_max_bytes=max_bytes),
        http_client=fake_http,
    )
    report = "\n".join(f"## 条目 {index}\n{'单细胞科研情报' * 25}" for index in range(80))

    result = await service.send_markdown(PushMessage(title="今日科研情报", markdown=report))

    assert result.chunks_sent == len(fake_http.calls)
    assert result.chunks_sent > 1
    assert len(report.encode("utf-8")) > 4096
    for call in fake_http.calls:
        payload = call["json"]
        content = payload["markdown"]["content"]
        assert payload["msgtype"] == "markdown"
        assert len(content.encode("utf-8")) <= max_bytes
    assert fake_http.calls[0]["json"]["markdown"]["content"].startswith("[1/")


def test_split_markdown_splits_single_oversized_line_safely() -> None:
    max_bytes = 700
    line = "https://example.com/" + ("单细胞" * 500)

    chunks = WeComPushService.split_markdown(line, title="今日科研情报", max_bytes=max_bytes)

    assert len(chunks) > 1
    assert all(len(chunk.encode("utf-8")) <= max_bytes for chunk in chunks)
    assert all(chunk for chunk in chunks)


@pytest.mark.anyio
async def test_send_markdown_errcode_40058_has_clear_sanitized_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=super-secret-key"
    fake_http = FakeHTTPClient(
        [
            wecom_response(
                {"errcode": 40058, "errmsg": "markdown content too long super-secret-upstream-detail"},
                secret_url,
            )
        ]
    )
    service = WeComPushService(
        settings=make_settings(webhook_url=secret_url, markdown_max_bytes=1000),
        http_client=fake_http,
    )

    with pytest.raises(WeComPushError, match="errcode=40058") as exc_info:
        await service.send_markdown(PushMessage(title="今日科研情报", markdown="短报告"))

    error_message = str(exc_info.value)
    assert "Markdown content is too long" in error_message
    assert "super-secret-key" not in error_message
    assert "super-secret-upstream-detail" not in error_message
    assert "super-secret-key" not in caplog.text


@pytest.mark.anyio
async def test_missing_wecom_webhook_url_gives_clear_error_without_http_call() -> None:
    fake_http = FakeHTTPClient()
    service = WeComPushService(
        settings=make_settings(webhook_url=None),
        http_client=fake_http,
    )

    with pytest.raises(MissingWeComConfigError, match="WECOM_WEBHOOK_URL"):
        await service.send_markdown(PushMessage(title="今日科研情报", markdown="短报告"))

    assert fake_http.calls == []
