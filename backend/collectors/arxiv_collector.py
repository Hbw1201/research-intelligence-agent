from backend.collectors.base import BaseCollector, CollectedItem


class ArxivCollector(BaseCollector):
    """Placeholder arXiv collector."""

    name = "arxiv"

    async def collect(self) -> list[CollectedItem]:
        raise NotImplementedError("arXiv collection will be implemented in the collector pass.")
