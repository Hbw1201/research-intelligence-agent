from dataclasses import dataclass


@dataclass(frozen=True)
class PushMessage:
    """Message payload for WeCom delivery."""

    title: str
    markdown: str


class WeComPushService:
    """Placeholder WeCom group robot webhook service."""

    async def send_markdown(self, message: PushMessage) -> None:
        raise NotImplementedError("WeCom webhook delivery will be implemented later.")
