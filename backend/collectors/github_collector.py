from backend.collectors.base import BaseCollector, CollectedItem


class GitHubCollector(BaseCollector):
    """Placeholder GitHub collector."""

    name = "github"

    async def collect(self) -> list[CollectedItem]:
        raise NotImplementedError("GitHub collection will be implemented in the collector pass.")
