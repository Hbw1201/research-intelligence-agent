from datetime import date, datetime, timezone
from typing import Any

import pytest

from backend.collectors.base import CollectorConfig
from backend.collectors.github_collector import GitHubCollector
from backend.config import get_settings
from scripts.run_daily_digest import build_collector_config


class FakeResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def json(self) -> dict[str, Any]:
        return self._data

    def raise_for_status(self) -> None:
        return None


class FakeGitHubClient:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.calls: list[dict[str, Any]] = []

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse({"items": self.items})


class FakeAsyncClient:
    calls: list[dict[str, Any]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls.append(kwargs)

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"items": []})


def fake_repo(repo_id: int, full_name: str = "openai/example") -> dict[str, Any]:
    return {
        "id": repo_id,
        "name": full_name.split("/")[-1],
        "full_name": full_name,
        "description": "  Research code\nrepository  ",
        "html_url": f"https://github.com/{full_name}",
        "owner": {"login": full_name.split("/")[0]},
        "stargazers_count": 42,
        "forks_count": 7,
        "updated_at": "2026-05-18T12:30:00Z",
        "language": "Python",
        "topics": ["agents", "research"],
    }


@pytest.mark.anyio
async def test_github_collector_empty_results() -> None:
    collector = GitHubCollector(client=FakeGitHubClient([]))

    items = await collector.collect(query="multi agent research", max_results=5)

    assert items == []


@pytest.mark.anyio
async def test_github_collector_normalizes_repository() -> None:
    collector = GitHubCollector(client=FakeGitHubClient([fake_repo(1)]))

    items = await collector.collect(query="research agents", max_results=1)

    assert len(items) == 1
    item = items[0]
    assert item.title == "openai/example"
    assert item.abstract == "Research code repository"
    assert item.url == "https://github.com/openai/example"
    assert item.source_name == "github"
    assert item.source_type == "code"
    assert item.item_type == "repository"
    assert item.authors == ["openai"]
    assert item.published_at == datetime(2026, 5, 18, 12, 30, tzinfo=timezone.utc)
    assert item.external_id == "1"
    assert item.keywords == ["agents", "research", "Python"]
    assert item.metadata["owner"] == "openai"
    assert item.metadata["stars"] == 42
    assert item.metadata["language"] == "Python"
    assert item.metadata["topics"] == ["agents", "research"]


@pytest.mark.anyio
async def test_github_collector_max_results_and_date_query() -> None:
    client = FakeGitHubClient([fake_repo(1), fake_repo(2, "openai/second"), fake_repo(3, "openai/third")])
    collector = GitHubCollector(client=client)

    items = await collector.collect(
        query="rag",
        max_results=2,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 18),
    )

    assert len(items) == 2
    params = client.calls[0]["params"]
    assert params["per_page"] == 2
    assert params["q"] == "rag pushed:2026-05-01..2026-05-18"


@pytest.mark.anyio
async def test_github_collector_passes_explicit_proxy_to_async_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.github_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = GitHubCollector(
        config=CollectorConfig(
            proxy=" http://127.0.0.1:7897 ",
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    items = await collector.collect(query="single-cell", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [
        {
            "timeout": 20.0,
            "proxy": "http://127.0.0.1:7897",
            "trust_env": False,
        }
    ]


@pytest.mark.anyio
async def test_github_collector_uses_https_proxy_when_generic_proxy_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.github_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = GitHubCollector(
        config=CollectorConfig(
            http_proxy="http://127.0.0.1:7898",
            https_proxy="http://127.0.0.1:7899",
        )
    )

    await collector.collect(query="single-cell", max_results=1)

    assert FakeAsyncClient.calls[0]["proxy"] == "http://127.0.0.1:7899"
    assert FakeAsyncClient.calls[0]["trust_env"] is False


@pytest.mark.anyio
async def test_github_collector_preserves_default_async_client_behavior_without_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setattr("backend.collectors.github_collector.httpx.AsyncClient", FakeAsyncClient)
    collector = GitHubCollector(config=CollectorConfig())

    items = await collector.collect(query="single-cell", max_results=1)

    assert items == []
    assert FakeAsyncClient.calls == [{"timeout": 20.0}]


def test_collector_proxy_env_vars_are_loaded_into_collector_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLLECTOR_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("COLLECTOR_HTTP_PROXY", "http://127.0.0.1:7898")
    monkeypatch.setenv("COLLECTOR_HTTPS_PROXY", "http://127.0.0.1:7899")
    get_settings.cache_clear()

    try:
        config = build_collector_config()
    finally:
        get_settings.cache_clear()

    assert config.proxy == "http://127.0.0.1:7897"
    assert config.http_proxy == "http://127.0.0.1:7898"
    assert config.https_proxy == "http://127.0.0.1:7899"
