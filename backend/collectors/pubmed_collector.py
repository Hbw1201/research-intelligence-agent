from backend.collectors.base import BaseCollector, CollectedItem


class PubMedCollector(BaseCollector):
    """Placeholder PubMed collector."""

    name = "pubmed"

    async def collect(self) -> list[CollectedItem]:
        raise NotImplementedError("PubMed collection will be implemented in the collector pass.")
