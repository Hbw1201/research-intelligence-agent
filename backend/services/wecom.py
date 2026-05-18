from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx

from backend.config import Settings, get_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PushMessage:
    """Message payload for WeCom delivery."""

    title: str
    markdown: str


@dataclass(frozen=True)
class WeComPushResult:
    """Sanitized result returned by a WeCom group robot webhook."""

    errcode: int
    errmsg: str


class WeComPushError(RuntimeError):
    """Base error for WeCom webhook delivery failures."""


class MissingWeComConfigError(WeComPushError):
    """Raised when the WeCom webhook URL is not configured."""


class InvalidWeComResponseError(WeComPushError):
    """Raised when WeCom returns a response that cannot be parsed safely."""


class WeComPushService:
    """WeCom group robot webhook service for markdown digest delivery."""

    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | Any | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client
        self._webhook_url_override = webhook_url

    async def send_markdown(self, message: PushMessage) -> WeComPushResult:
        """Push a markdown message to the configured WeCom group robot."""
        content = message.markdown.strip()
        if not content:
            raise ValueError("WeCom markdown content must not be empty.")

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
            },
        }
        return await self._post_payload(payload, message_title=message.title, content_bytes=len(content.encode("utf-8")))

    async def _post_payload(
        self,
        payload: dict[str, Any],
        message_title: str,
        content_bytes: int,
    ) -> WeComPushResult:
        webhook_url = self._webhook_url()
        attempts = max(1, self.settings.wecom_max_retries)
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            logger.info(
                "Pushing WeCom markdown message title=%s content_bytes=%s attempt=%s/%s",
                message_title,
                content_bytes,
                attempt,
                attempts,
                extra={
                    "message_title": message_title,
                    "content_bytes": content_bytes,
                    "attempt": attempt,
                    "max_attempts": attempts,
                },
            )
            try:
                response = await self._post(webhook_url, payload)
                self._raise_for_status(response)
                return self._parse_response(response)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                self._log_retry("Transient WeCom webhook transport error; retrying", message_title, attempt, attempts)
            except httpx.HTTPStatusError as exc:
                if not self._is_transient_status(exc.response.status_code):
                    raise WeComPushError(f"WeCom webhook returned HTTP {exc.response.status_code}.") from exc
                last_error = exc
                if attempt >= attempts:
                    break
                self._log_retry("Transient WeCom webhook HTTP error; retrying", message_title, attempt, attempts)

        if isinstance(last_error, httpx.HTTPStatusError):
            raise WeComPushError(f"WeCom webhook returned HTTP {last_error.response.status_code}.") from last_error
        raise WeComPushError("WeCom webhook request failed after retries.") from last_error

    async def _post(self, webhook_url: str, payload: dict[str, Any]) -> httpx.Response:
        timeout = self.settings.wecom_timeout_seconds
        if self._http_client is not None:
            return await self._http_client.post(webhook_url, json=payload, timeout=timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(webhook_url, json=payload)

    def _webhook_url(self) -> str:
        if self._webhook_url_override is not None:
            webhook_url = self._webhook_url_override.strip()
        else:
            secret = self.settings.wecom_webhook_url
            webhook_url = secret.get_secret_value().strip() if secret else ""

        if not webhook_url:
            raise MissingWeComConfigError("WECOM_WEBHOOK_URL is required.")
        return webhook_url

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise exc

    @staticmethod
    def _parse_response(response: httpx.Response) -> WeComPushResult:
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidWeComResponseError("WeCom webhook returned an invalid JSON response.") from exc

        if not isinstance(data, dict):
            raise InvalidWeComResponseError("WeCom webhook returned an invalid response shape.")

        errcode = data.get("errcode")
        errmsg = data.get("errmsg", "")
        if not isinstance(errcode, int) or not isinstance(errmsg, str):
            raise InvalidWeComResponseError("WeCom webhook returned an invalid response shape.")

        result = WeComPushResult(errcode=errcode, errmsg=errmsg)
        if errcode != 0:
            raise WeComPushError(f"WeCom webhook rejected message with errcode={errcode}.")
        return result

    @staticmethod
    def _is_transient_status(status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}

    @staticmethod
    def _log_retry(message: str, message_title: str, attempt: int, max_attempts: int) -> None:
        logger.warning(
            "%s title=%s attempt=%s/%s",
            message,
            message_title,
            attempt,
            max_attempts,
            extra={
                "message_title": message_title,
                "attempt": attempt,
                "max_attempts": max_attempts,
            },
        )
