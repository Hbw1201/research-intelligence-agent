from backend.collectors.base import BaseCollector, CollectedItem


class RSSCollector(BaseCollector):
    """Placeholder RSS collector."""

    name = "rss"

    async def collect(self) -> list[CollectedItem]:
        raise NotImplementedError("RSS collection will be implemented in the collector pass.")
