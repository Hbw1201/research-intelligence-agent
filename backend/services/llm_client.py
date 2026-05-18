from dataclasses import dataclass
from typing import Protocol

from backend.config import Settings


@dataclass(frozen=True)
class LLMRequest:
    """Provider-agnostic LLM completion request."""

    system_prompt: str
    user_prompt: str
    temperature: float = 0.2


class LLMClient(Protocol):
    """Protocol for external LLM providers."""

    async def complete(self, request: LLMRequest) -> str:
        """Return generated text for the request."""


class ExternalLLMClient:
    """Placeholder unified LLM client."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def complete(self, request: LLMRequest) -> str:
        raise NotImplementedError("External LLM integration will be implemented later.")
