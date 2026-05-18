from datetime import date, datetime, timezone
from typing import Any

import pytest

from backend.collectors.github_collector import GitHubCollector


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
