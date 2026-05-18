from backend.collectors.base import CollectedItem


class RelevanceRanker:
    """Placeholder relevance ranking service."""

    async def rank(self, items: list[CollectedItem], profile_id: str) -> list[CollectedItem]:
        raise NotImplementedError("Relevance ranking will be implemented later.")
