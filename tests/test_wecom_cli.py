from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.collectors.base import ResearchItem
from backend.config import Settings
from backend.services.digest_service import DigestItem
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


def make_research_item(title: str = "Included item") -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract="Summary",
        url="https://example.com/included",
        source_name="web",
        source_type="paper",
        item_type="paper",
        authors=[],
        published_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        raw_text="Summary",
        external_id=None,
        keywords=[],
        metadata={},
    )


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


def test_run_daily_digest_parse_args_accepts_source_registry_option(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_daily_digest.py",
            "--keywords",
            "single-cell",
            "--update-source-registry",
        ],
    )

    args = run_daily_digest.parse_args()

    assert args.update_source_registry is True


def test_run_daily_digest_parse_args_accepts_html_report_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_daily_digest.py",
            "--keywords",
            "single-cell",
            "--html-report",
            "--push-link-only",
        ],
    )

    args = run_daily_digest.parse_args()

    assert args.html_report is True
    assert args.push_link_only is True


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


@pytest.mark.anyio
async def test_run_daily_digest_forwards_update_source_registry_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            captured["init"] = kwargs

        async def run(self, **kwargs: Any) -> Any:
            captured["run"] = kwargs
            return SimpleNamespace(report="# Daily", output_path=None, included_items=[])

    monkeypatch.setattr(
        run_daily_digest,
        "parse_args",
        lambda: Namespace(
            keywords="single-cell",
            user_profile=None,
            max_items=5,
            sources="web",
            rss_feed_url=[],
            output_path=None,
            push_wecom=False,
            wecom_title="Daily",
            update_source_registry=True,
        ),
    )
    monkeypatch.setattr(run_daily_digest, "build_collectors", lambda sources, rss_feed_urls: {})
    monkeypatch.setattr(run_daily_digest, "ExternalLLMClient", lambda: object())
    monkeypatch.setattr(run_daily_digest, "ChineseDigestService", lambda llm_client: object())
    monkeypatch.setattr(run_daily_digest, "DailyIntelligencePipeline", FakePipeline)

    await run_daily_digest.run()

    assert captured["init"]["source_registry"] is not None
    assert captured["run"]["update_source_registry"] is True


@pytest.mark.anyio
async def test_run_daily_digest_push_link_only_message_includes_count_titles_and_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = FakePushService()
    digests = [
        DigestItem(
            title=f"Top item {index}",
            item_type="paper",
            source_name="web",
            url=f"https://example.com/{index}",
            one_sentence_summary="Summary",
            key_points=[],
            relevance_reason="Relevant",
            recommended_action="Read",
            importance_level="medium",
        )
        for index in range(1, 5)
    ]

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                report="# Daily",
                output_path=None,
                included_items=[make_research_item()],
                digests=digests,
                collector_errors={},
                deduplication_summary=None,
            )

    monkeypatch.setattr(
        run_daily_digest,
        "parse_args",
        lambda: Namespace(
            keywords="single-cell",
            user_profile=None,
            max_items=5,
            sources="web",
            rss_feed_url=[],
            output_path=None,
            push_wecom=True,
            wecom_title="Daily",
            update_source_registry=False,
            html_report=True,
            push_link_only=True,
        ),
    )
    monkeypatch.setattr(run_daily_digest, "build_collectors", lambda sources, rss_feed_urls: {})
    monkeypatch.setattr(run_daily_digest, "ExternalLLMClient", lambda: object())
    monkeypatch.setattr(run_daily_digest, "ChineseDigestService", lambda llm_client: object())
    monkeypatch.setattr(run_daily_digest, "DailyIntelligencePipeline", FakePipeline)
    monkeypatch.setattr(run_daily_digest, "WeComPushService", lambda: service)
    monkeypatch.setenv("REPORT_SITE_DIR", str(tmp_path / "site"))
    monkeypatch.setenv("REPORT_PUBLIC_BASE_URL", "https://reports.example.com/reports")
    run_daily_digest.get_settings.cache_clear()

    try:
        await run_daily_digest.run()
    finally:
        run_daily_digest.get_settings.cache_clear()

    assert len(service.markdown_messages) == 1
    markdown = service.markdown_messages[0].markdown
    assert "今日科研情报已更新" in markdown
    assert "共 4 条" in markdown
    assert "Top item 1" in markdown
    assert "Top item 3" in markdown
    assert "Top item 4" not in markdown
    assert "阅读全文：https://reports.example.com/reports/latest.html" in markdown
    assert (tmp_path / "site" / "latest.html").exists()


@pytest.mark.anyio
async def test_run_daily_digest_missing_public_base_url_saves_html_but_skips_link_push(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    service = FakePushService()

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, **kwargs: Any) -> Any:
            return SimpleNamespace(
                report="# Daily",
                output_path=None,
                included_items=[make_research_item()],
                digests=[
                    DigestItem(
                        title="Only item",
                        item_type="paper",
                        source_name="web",
                        url="https://example.com/1",
                        one_sentence_summary="Summary",
                        key_points=[],
                        relevance_reason="Relevant",
                        recommended_action="Read",
                        importance_level="medium",
                    )
                ],
                collector_errors={},
                deduplication_summary=None,
            )

    monkeypatch.setattr(
        run_daily_digest,
        "parse_args",
        lambda: Namespace(
            keywords="single-cell",
            user_profile=None,
            max_items=5,
            sources="web",
            rss_feed_url=[],
            output_path=None,
            push_wecom=True,
            wecom_title="Daily",
            update_source_registry=False,
            html_report=True,
            push_link_only=True,
        ),
    )
    monkeypatch.setattr(run_daily_digest, "build_collectors", lambda sources, rss_feed_urls: {})
    monkeypatch.setattr(run_daily_digest, "ExternalLLMClient", lambda: object())
    monkeypatch.setattr(run_daily_digest, "ChineseDigestService", lambda llm_client: object())
    monkeypatch.setattr(run_daily_digest, "DailyIntelligencePipeline", FakePipeline)
    monkeypatch.setattr(run_daily_digest, "WeComPushService", lambda: service)
    monkeypatch.setenv("REPORT_SITE_DIR", str(tmp_path / "site"))
    monkeypatch.setenv("REPORT_PUBLIC_BASE_URL", "")
    run_daily_digest.get_settings.cache_clear()

    try:
        await run_daily_digest.run()
    finally:
        run_daily_digest.get_settings.cache_clear()

    output = capsys.readouterr().out
    assert "Saved HTML report:" in output
    assert "No public report URL configured" in output
    assert "Skipped WeCom push-link-only" in output
    assert "Local HTML report:" in output
    assert len(service.markdown_messages) == 0
    assert (tmp_path / "site" / "latest.html").exists()


def test_build_link_only_wecom_message_uses_top_three_titles() -> None:
    message = run_daily_digest.build_link_only_wecom_message(
        count=5,
        titles=["A", "B", "C", "D"],
        report_url="https://reports.example.com/latest.html",
    )

    assert message == "今日科研情报已更新\n共 5 条\n\n- A\n- B\n- C\n\n阅读全文：https://reports.example.com/latest.html"
