from dataclasses import dataclass
import logging
from typing import Any, Protocol

import httpx

from backend.config import Settings, get_settings


logger = logging.getLogger(__name__)


CHEAP_TASKS = {"screening", "tagging"}
STANDARD_TASKS = {"summarization", "ranking"}
STRONG_TASKS = {"weekly_report", "deep_analysis"}
DEFAULT_SYSTEM_PROMPT = "You are a concise research intelligence assistant."
MAX_TOKEN_TOO_LARGE_FALLBACKS = (8192, 4096, 2048)


@dataclass(frozen=True)
class LLMRequest:
    """Provider-agnostic LLM completion request."""

    prompt: str = ""
    task_type: str = "summarization"
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    user_prompt: str | None = None


class LLMClient(Protocol):
    """Protocol for external LLM providers."""

    async def complete(
        self,
        prompt: str | LLMRequest,
        task_type: str = "summarization",
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return generated text for the request."""


class LLMClientError(RuntimeError):
    """Base error for LLM client failures."""


class MissingLLMConfigError(LLMClientError):
    """Raised when required LLM configuration is missing."""


class InvalidLLMResponseError(LLMClientError):
    """Raised when the relay response does not match chat completions format."""


class TruncatedLLMResponseError(InvalidLLMResponseError):
    """Raised when the relay stops before producing final user-facing content."""


LLMTruncatedResponseError = TruncatedLLMResponseError


class _MaxTokensTooLargeError(LLMClientError):
    """Internal signal for provider-side max_tokens limit rejections."""


class ExternalLLMClient:
    """OpenAI-compatible chat completions client for the internal relay."""

    def __init__(self, settings: Settings | None = None, http_client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._http_client = http_client

    async def complete(
        self,
        prompt: str | LLMRequest,
        task_type: str = "summarization",
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Complete a prompt through the OpenAI-compatible chat endpoint."""
        request = self._coerce_request(prompt, task_type, system_prompt, temperature, max_tokens)
        api_key = self._api_key()
        model = self.select_model(request.task_type)
        payload = self._payload(request, model, self.select_max_tokens(request.task_type))
        attempts = max(1, self.settings.llm_max_retries)

        last_error: Exception | None = None
        transient_attempt = 1
        while transient_attempt <= attempts:
            logger.info(
                "Calling LLM relay provider=%s model=%s task_type=%s max_tokens=%s attempt=%s/%s",
                self.settings.llm_provider,
                model,
                request.task_type,
                payload.get("max_tokens"),
                transient_attempt,
                attempts,
                extra={
                    "provider": self.settings.llm_provider,
                    "model": model,
                    "task_type": request.task_type,
                    "max_tokens": payload.get("max_tokens"),
                    "attempt": transient_attempt,
                    "max_attempts": attempts,
                },
            )
            try:
                response = await self._post(payload, api_key)
                if self._is_max_tokens_too_large_response(response):
                    self._apply_max_tokens_fallback(payload, model, request.task_type, response.status_code)
                    continue

                self._raise_for_status(response)
                return self._parse_response(response)
            except _MaxTokensTooLargeError:
                self._apply_max_tokens_fallback(payload, model, request.task_type)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if transient_attempt >= attempts:
                    break
                logger.warning(
                    "Transient LLM relay error; retrying provider=%s model=%s task_type=%s max_tokens=%s",
                    self.settings.llm_provider,
                    model,
                    request.task_type,
                    payload.get("max_tokens"),
                    extra={
                        "provider": self.settings.llm_provider,
                        "model": model,
                        "task_type": request.task_type,
                        "max_tokens": payload.get("max_tokens"),
                    },
                )
                transient_attempt += 1
            except httpx.HTTPStatusError as exc:
                if self._is_max_tokens_too_large_response(exc.response):
                    self._apply_max_tokens_fallback(payload, model, request.task_type, exc.response.status_code)
                    continue

                if not self._is_transient_status(exc.response.status_code):
                    raise LLMClientError(
                        f"LLM relay returned HTTP {exc.response.status_code}."
                    ) from exc
                last_error = exc
                if transient_attempt >= attempts:
                    break
                logger.warning(
                    "Transient LLM relay HTTP error; retrying provider=%s model=%s task_type=%s max_tokens=%s status_code=%s",
                    self.settings.llm_provider,
                    model,
                    request.task_type,
                    payload.get("max_tokens"),
                    exc.response.status_code,
                    extra={
                        "provider": self.settings.llm_provider,
                        "model": model,
                        "task_type": request.task_type,
                        "max_tokens": payload.get("max_tokens"),
                        "status_code": exc.response.status_code,
                    },
                )
                transient_attempt += 1

        if isinstance(last_error, httpx.HTTPStatusError):
            raise LLMClientError(f"LLM relay returned HTTP {last_error.response.status_code}.") from last_error
        raise LLMClientError("LLM relay request failed after retries.") from last_error

    def select_model(self, task_type: str) -> str:
        """Select the configured model for a task route."""
        normalized_task = task_type.strip().lower()
        if normalized_task in CHEAP_TASKS:
            return self.settings.llm_model_cheap
        if normalized_task in STRONG_TASKS:
            return self.settings.llm_model_strong
        return self.settings.llm_model_standard

    def select_max_tokens(self, task_type: str) -> int:
        """Select the configured max token budget for a task route."""
        normalized_task = task_type.strip().lower()
        if normalized_task in CHEAP_TASKS:
            return self.settings.llm_max_tokens_cheap
        if normalized_task in STANDARD_TASKS:
            return self.settings.llm_max_tokens_standard
        if normalized_task in STRONG_TASKS:
            return self.settings.llm_max_tokens_strong
        return self.settings.llm_max_tokens

    def _apply_max_tokens_fallback(
        self,
        payload: dict[str, object],
        model: str,
        task_type: str,
        status_code: int | None = None,
    ) -> None:
        current_max_tokens = payload.get("max_tokens")
        fallback_max_tokens = self._next_max_tokens_fallback(current_max_tokens)
        if fallback_max_tokens is None:
            raise LLMClientError(
                "LLM relay rejected max_tokens as too large after fallback retries. "
                f"last_max_tokens={current_max_tokens}"
            )

        logger.warning(
            "LLM relay rejected max_tokens; retrying provider=%s model=%s task_type=%s max_tokens=%s fallback_max_tokens=%s status_code=%s",
            self.settings.llm_provider,
            model,
            task_type,
            current_max_tokens,
            fallback_max_tokens,
            status_code,
            extra={
                "provider": self.settings.llm_provider,
                "model": model,
                "task_type": task_type,
                "max_tokens": current_max_tokens,
                "fallback_max_tokens": fallback_max_tokens,
                "status_code": status_code,
            },
        )
        payload["max_tokens"] = fallback_max_tokens

    async def _post(self, payload: dict[str, object], api_key: str) -> httpx.Response:
        base_url = (self.settings.llm_base_url or "").rstrip("/")
        if not base_url:
            raise MissingLLMConfigError("LLM_BASE_URL is required.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        url = f"{base_url}/chat/completions"
        timeout = self.settings.llm_timeout_seconds

        if self._http_client is not None:
            return await self._http_client.post(url, json=payload, headers=headers, timeout=timeout)

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload, headers=headers)

    def _api_key(self) -> str:
        secret = self.settings.llm_api_key
        value = secret.get_secret_value().strip() if secret else ""
        if not value:
            raise MissingLLMConfigError("LLM_API_KEY is required.")
        return value

    @classmethod
    def _coerce_request(
        cls,
        prompt: str | LLMRequest,
        task_type: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> LLMRequest:
        if isinstance(prompt, LLMRequest):
            return LLMRequest(
                prompt=prompt.prompt or prompt.user_prompt or "",
                task_type=prompt.task_type,
                system_prompt=prompt.system_prompt,
                temperature=prompt.temperature,
                max_tokens=max_tokens if max_tokens is not None else prompt.max_tokens,
            )
        return LLMRequest(
            prompt=prompt,
            task_type=task_type,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    @staticmethod
    def _payload(request: LLMRequest, model: str, default_max_tokens: int | None = None) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": model,
            "messages": [
                {"role": "system", "content": request.system_prompt or DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": request.prompt},
            ],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        effective_max_tokens = request.max_tokens if request.max_tokens is not None else default_max_tokens
        if effective_max_tokens is not None and effective_max_tokens > 0:
            payload["max_tokens"] = effective_max_tokens
        return payload

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise exc

    @staticmethod
    def _parse_response(response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidLLMResponseError("LLM relay returned an invalid chat completion response.") from exc

        if not isinstance(data, dict):
            raise InvalidLLMResponseError("LLM relay returned an invalid chat completion response.")

        if "error" in data:
            if ExternalLLMClient._is_max_tokens_too_large_data(data):
                raise _MaxTokensTooLargeError("LLM relay rejected max_tokens as too large.")
            raise LLMClientError(
                f"LLM relay returned an error object. shape={ExternalLLMClient._response_shape(data)}"
            )

        parsed_content = ExternalLLMClient._extract_response_text(data)
        if parsed_content is not None:
            return parsed_content

        raise InvalidLLMResponseError(
            f"LLM relay returned chat completion content that could not be parsed as text. "
            f"shape={ExternalLLMClient._response_shape(data)}"
        )

    @staticmethod
    def _extract_response_text(data: dict[str, Any]) -> str | None:
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                raw_content = message.get("content")
                content = ExternalLLMClient._content_to_text(raw_content)
                if content:
                    return content

                if ExternalLLMClient._is_truncated_empty_content(choice, raw_content, content):
                    raise TruncatedLLMResponseError(
                        "LLM response was truncated before final content was produced. "
                        "Increase LLM_MAX_TOKENS. "
                        f"shape={ExternalLLMClient._response_shape(data)}"
                    )

            choice_text = ExternalLLMClient._content_to_text(choice.get("text"))
            if choice_text:
                return choice_text

        output_text = ExternalLLMClient._content_to_text(data.get("output_text"))
        if output_text:
            return output_text

        return None

    @staticmethod
    def _content_to_text(content: Any) -> str | None:
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                text = ExternalLLMClient._content_part_to_text(part)
                if text is None:
                    return None
                parts.append(text)
            return "".join(parts)

        if isinstance(content, dict):
            return ExternalLLMClient._content_part_to_text(content)

        return None

    @staticmethod
    def _content_part_to_text(part: Any) -> str | None:
        if isinstance(part, str):
            return part
        if not isinstance(part, dict):
            return None

        text = part.get("text")
        if isinstance(text, str):
            return text

        nested_content = part.get("content")
        if isinstance(nested_content, str):
            return nested_content

        return None

    @staticmethod
    def _response_shape(data: dict[str, Any]) -> dict[str, Any]:
        shape: dict[str, Any] = {
            "top_level_keys": ExternalLLMClient._safe_keys(data),
        }
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        if not isinstance(choice, dict):
            shape["choice_type"] = type(choice).__name__
            return shape

        shape["choice_keys"] = ExternalLLMClient._safe_keys(choice)
        shape["finish_reason"] = choice.get("finish_reason")
        message = choice.get("message")
        if not isinstance(message, dict):
            shape["message_type"] = type(message).__name__
            return shape

        content = message.get("content")
        shape["message_keys"] = ExternalLLMClient._safe_keys(message)
        shape["content_type"] = type(content).__name__
        return shape

    @staticmethod
    def _safe_keys(data: dict[str, Any]) -> list[str]:
        return sorted(str(key) for key in data.keys() if "reasoning" not in str(key).lower())

    @staticmethod
    def _is_truncated_empty_content(choice: dict[str, Any], raw_content: Any, parsed_content: str | None) -> bool:
        if choice.get("finish_reason") != "length":
            return False
        if parsed_content:
            return False
        return raw_content is None or raw_content == "" or raw_content == []

    @staticmethod
    def _next_max_tokens_fallback(current_max_tokens: object) -> int | None:
        if not isinstance(current_max_tokens, int) or current_max_tokens <= 0:
            return MAX_TOKEN_TOO_LARGE_FALLBACKS[0]
        for fallback_max_tokens in MAX_TOKEN_TOO_LARGE_FALLBACKS:
            if fallback_max_tokens < current_max_tokens:
                return fallback_max_tokens
        return None

    @staticmethod
    def _is_max_tokens_too_large_response(response: httpx.Response) -> bool:
        try:
            data = response.json()
        except ValueError:
            return False
        if not isinstance(data, dict):
            return False
        if "error" in data:
            return ExternalLLMClient._is_max_tokens_too_large_data(data)
        if response.status_code >= 400:
            return ExternalLLMClient._looks_like_max_tokens_too_large(
                ExternalLLMClient._collect_error_strings(data)
            )
        return False

    @staticmethod
    def _is_max_tokens_too_large_data(data: dict[str, Any]) -> bool:
        error = data.get("error", data)
        return ExternalLLMClient._looks_like_max_tokens_too_large(
            ExternalLLMClient._collect_error_strings(error)
        )

    @staticmethod
    def _collect_error_strings(value: Any) -> list[str]:
        strings: list[str] = []
        if isinstance(value, str):
            strings.append(value)
        elif isinstance(value, dict):
            for nested in value.values():
                strings.extend(ExternalLLMClient._collect_error_strings(nested))
        elif isinstance(value, list):
            for nested in value:
                strings.extend(ExternalLLMClient._collect_error_strings(nested))
        return strings

    @staticmethod
    def _looks_like_max_tokens_too_large(strings: list[str]) -> bool:
        text = " ".join(strings).lower()
        if not text:
            return False

        token_references = ("max_tokens", "max tokens", "maximum tokens", "token limit", "tokens")
        limit_references = (
            "too large",
            "exceed",
            "exceeds",
            "exceeded",
            "greater than",
            "less than or equal",
            "maximum",
            "at most",
            "limit",
        )
        return any(reference in text for reference in token_references) and any(
            reference in text for reference in limit_references
        )

    @staticmethod
    def _is_transient_status(status_code: int) -> bool:
        return status_code in {408, 429, 500, 502, 503, 504}
