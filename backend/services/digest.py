from backend.collectors.base import CollectedItem
from backend.services.llm_client import LLMClient


class ChineseDigestService:
    """Placeholder Chinese digest generation service."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def generate(self, items: list[CollectedItem]) -> str:
        raise NotImplementedError("Chinese digest generation will be implemented later.")
