from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import httpx

from backend.config import Settings, get_settings


logger = logging.getLogger(__name__)


DEFAULT_MARKDOWN_MAX_BYTES = 3500
MIN_MARKDOWN_MAX_BYTES = 512
WECOM_MARKDOWN_TOO_LONG_ERRCODE = 40058


@dataclass(frozen=True)
class PushMessage:
    """Message payload for WeCom delivery."""

    title: str
    markdown: str


@dataclass(frozen=True)
class WeComPushResult:
    """Sanitized result returned by WeCom group robot webhook delivery."""

    errcode: int
    errmsg: str
    chunks_sent: int = 1


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

        chunks = self.split_markdown(content, message.title, max_bytes=self._markdown_max_bytes())
        last_result: WeComPushResult | None = None
        for chunk in chunks:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": chunk,
                },
            }
            last_result = await self._post_payload(
                payload,
                message_title=message.title,
                content_bytes=self._byte_len(chunk),
            )

        return WeComPushResult(
            errcode=last_result.errcode if last_result else 0,
            errmsg=last_result.errmsg if last_result else "ok",
            chunks_sent=len(chunks),
        )

    async def send_text(self, message: PushMessage) -> WeComPushResult:
        """Push a plain text message to the configured WeCom group robot."""
        content = message.markdown.strip()
        if not content:
            raise ValueError("WeCom text content must not be empty.")

        payload = {
            "msgtype": "text",
            "text": {
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

        if errcode != 0:
            if errcode == WECOM_MARKDOWN_TOO_LONG_ERRCODE:
                raise WeComPushError(
                    "WeCom webhook rejected message with errcode=40058. "
                    "Markdown content is too long; reduce WECOM_MARKDOWN_MAX_BYTES or split the report further."
                )
            raise WeComPushError(f"WeCom webhook rejected message with errcode={errcode}.")
        return WeComPushResult(errcode=errcode, errmsg=errmsg)

    @classmethod
    def split_markdown(cls, content: str, title: str, max_bytes: int = DEFAULT_MARKDOWN_MAX_BYTES) -> list[str]:
        """Split markdown into WeCom-safe chunks measured by UTF-8 bytes."""
        normalized = content.strip()
        if not normalized:
            return []

        safe_max_bytes = max(MIN_MARKDOWN_MAX_BYTES, max_bytes)
        chunks = cls._split_markdown_body_with_header_budget(normalized, title, safe_max_bytes)
        for _ in range(10):
            final_chunks = [
                cls._with_chunk_header(chunk, index, len(chunks), title, safe_max_bytes)
                for index, chunk in enumerate(chunks, start=1)
            ]
            if all(cls._byte_len(chunk) <= safe_max_bytes for chunk in final_chunks):
                return final_chunks

            chunks = cls._split_body(
                normalized,
                cls._body_max_bytes_for_header(len(chunks) + 1, title, safe_max_bytes),
            )

        raise WeComPushError("Unable to split WeCom markdown content under the byte limit.")

    @classmethod
    def _split_markdown_body_with_header_budget(cls, content: str, title: str, max_bytes: int) -> list[str]:
        estimated_total = 1
        chunks = [content]
        for _ in range(10):
            body_max_bytes = cls._body_max_bytes_for_header(estimated_total, title, max_bytes)
            chunks = cls._split_body(content, body_max_bytes)
            if len(chunks) == estimated_total:
                break
            estimated_total = len(chunks)
        return chunks

    @classmethod
    def _split_body(cls, content: str, max_bytes: int) -> list[str]:
        chunks: list[str] = []
        current = ""
        for line in content.splitlines():
            pieces = cls._split_long_line(line, max_bytes)
            for piece in pieces:
                candidate = piece if not current else f"{current}\n{piece}"
                if cls._byte_len(candidate) <= max_bytes:
                    current = candidate
                    continue

                if current:
                    chunks.append(current)
                current = piece

        if current:
            chunks.append(current)
        return chunks or [content]

    @classmethod
    def _split_long_line(cls, line: str, max_bytes: int) -> list[str]:
        if cls._byte_len(line) <= max_bytes:
            return [line]

        parts: list[str] = []
        current = ""
        for token in cls._long_line_tokens(line):
            if cls._byte_len(token) > max_bytes:
                if current:
                    parts.append(current)
                    current = ""
                parts.extend(cls._split_text_by_bytes(token, max_bytes))
                continue

            candidate = token if not current else f"{current} {token}"
            if cls._byte_len(candidate) <= max_bytes:
                current = candidate
                continue

            if current:
                parts.append(current)
            current = token

        if current:
            parts.append(current)
        return parts

    @staticmethod
    def _long_line_tokens(line: str) -> list[str]:
        tokens = line.split()
        return tokens if tokens else [line]

    @classmethod
    def _with_chunk_header(
        cls,
        chunk: str,
        index: int,
        total_chunks: int,
        title: str,
        max_bytes: int,
    ) -> str:
        header = f"[{index}/{total_chunks}] {title}".strip()
        header_prefix = f"{header}\n\n"
        header_bytes = cls._byte_len(header_prefix)
        if header_bytes >= max_bytes:
            header = f"[{index}/{total_chunks}]"
            header_prefix = f"{header}\n\n"
        return f"{header_prefix}{chunk}"

    @classmethod
    def _body_max_bytes_for_header(cls, total_chunks: int, title: str, max_bytes: int) -> int:
        header = f"[{total_chunks}/{total_chunks}] {title}".strip()
        header_prefix = f"{header}\n\n"
        if cls._byte_len(header_prefix) >= max_bytes:
            header_prefix = f"[{total_chunks}/{total_chunks}]\n\n"
        return max(1, max_bytes - cls._byte_len(header_prefix))

    @classmethod
    def _split_text_by_bytes(cls, text: str, max_bytes: int) -> list[str]:
        parts: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if cls._byte_len(candidate) <= max_bytes:
                current = candidate
                continue
            if current:
                parts.append(current)
            current = char

        if current:
            parts.append(current)
        return parts

    def _markdown_max_bytes(self) -> int:
        return max(MIN_MARKDOWN_MAX_BYTES, self.settings.wecom_markdown_max_bytes)

    @staticmethod
    def _byte_len(value: str) -> int:
        return len(value.encode("utf-8"))

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
