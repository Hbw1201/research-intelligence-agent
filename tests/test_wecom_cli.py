from __future__ import annotations

from argparse import Namespace
from types import SimpleNamespace
from typing import Any

import pytest

from backend.config import Settings
from backend.services.wecom import PushMessage, WeComPushService
from scripts import push_report_wecom, run_daily_digest


class FakePushService:
    def __init__(self) -> None:
        self.markdown_messages: list[PushMessage] = []
        self.text_messages: list[PushMessage] = []

    async def send_markdown(self, message: PushMessage) -> None:
        self.markdown_messages.append(message)

    async def send_text(self, message: PushMessage) -> None:
        self.text_messages.append(message)


class RecordingHTTPClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, **kwargs: Any) -> Any:
        self.calls.append({"url": url, **kwargs})
        from tests.test_wecom_service import wecom_response

        return wecom_response({"errcode": 0, "errmsg": "ok"}, url)


@pytest.mark.anyio
async def test_push_report_wecom_cli_can_be_invoked_with_mocked_service(tmp_path: Any) -> None:
    report_path = tmp_path / "daily.md"
    report_path.write_text("# 今日科研情报\n\n单细胞更新", encoding="utf-8")
    service = FakePushService()

    exit_code = await push_report_wecom.run(
        [
            "--report-path",
            str(report_path),
            "--message-type",
            "markdown",
            "--title",
            "今日科研情报",
        ],
        service=service,
    )

    assert exit_code == 0
    assert len(service.markdown_messages) == 1
    assert service.markdown_messages[0].title == "今日科研情报"
    assert "单细胞更新" in service.markdown_messages[0].markdown


def test_run_daily_digest_parse_args_accepts_push_wecom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_daily_digest.py",
            "--keywords",
            "single-cell",
            "--push-wecom",
            "--wecom-title",
            "今日科研情报",
        ],
    )

    args = run_daily_digest.parse_args()

    assert args.push_wecom is True
    assert args.wecom_title == "今日科研情报"


def test_run_daily_digest_parse_args_accepts_seen_item_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_daily_digest.py",
            "--keywords",
            "single-cell",
            "--seen-store-path",
            "tmp/seen_items.jsonl",
            "--include-seen",
            "--mark-seen",
        ],
    )

    args = run_daily_digest.parse_args()

    assert args.seen_store_path == "tmp/seen_items.jsonl"
    assert args.include_seen is True
    assert args.mark_seen is True


@pytest.mark.anyio
async def test_run_daily_digest_push_wecom_uses_chunked_markdown_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_http = RecordingHTTPClient()
    settings = Settings(
        _env_file=None,
        wecom_webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-secret",
        wecom_timeout_seconds=5,
        wecom_max_retries=1,
        wecom_markdown_max_bytes=1000,
    )
    report = "\n".join(f"## 条目 {index}\n{'单细胞科研情报' * 25}" for index in range(80))

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def run(self, **kwargs: Any) -> Any:
            return SimpleNamespace(report=report, output_path=None)

    def make_service() -> WeComPushService:
        return WeComPushService(settings=settings, http_client=fake_http)

    monkeypatch.setattr(
        run_daily_digest,
        "parse_args",
        lambda: Namespace(
            keywords="single-cell",
            user_profile=None,
            max_items=5,
            sources="github",
            rss_feed_url=[],
            output_path=None,
            push_wecom=True,
            wecom_title="今日科研情报",
        ),
    )
    monkeypatch.setattr(run_daily_digest, "build_collectors", lambda sources, rss_feed_urls: {})
    monkeypatch.setattr(run_daily_digest, "ExternalLLMClient", lambda: object())
    monkeypatch.setattr(run_daily_digest, "ChineseDigestService", lambda llm_client: object())
    monkeypatch.setattr(run_daily_digest, "DailyIntelligencePipeline", FakePipeline)
    monkeypatch.setattr(run_daily_digest, "WeComPushService", make_service)

    await run_daily_digest.run()

    assert len(fake_http.calls) > 1
    for call in fake_http.calls:
        content = call["json"]["markdown"]["content"]
        assert len(content.encode("utf-8")) <= settings.wecom_markdown_max_bytes
