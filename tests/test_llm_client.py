from copy import deepcopy
from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.services.llm_client import (
    ExternalLLMClient,
    InvalidLLMResponseError,
    LLMClientError,
    MissingLLMConfigError,
    TruncatedLLMResponseError,
)


class FakeHTTPClient:
    def __init__(self, outcomes: list[httpx.Response | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.calls.append({"url": url, **deepcopy(kwargs)})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_settings(
    api_key: str | None = "test-api-key",
    max_retries: int = 3,
    max_tokens: int = 8192,
    max_tokens_cheap: int = 4096,
    max_tokens_standard: int = 8192,
    max_tokens_strong: int = 16384,
) -> Settings:
    return Settings(
        _env_file=None,
        llm_provider="zyai",
        llm_api_key=api_key,
        llm_base_url="http://relay.example/v1",
        llm_model_cheap="cheap-model",
        llm_model_standard="standard-model",
        llm_model_strong="strong-model",
        llm_timeout_seconds=5,
        llm_max_retries=max_retries,
        llm_max_tokens=max_tokens,
        llm_max_tokens_cheap=max_tokens_cheap,
        llm_max_tokens_standard=max_tokens_standard,
        llm_max_tokens_strong=max_tokens_strong,
    )


def chat_response(content: Any, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json={"choices": [{"message": {"content": content}}]},
        request=httpx.Request("POST", "http://relay.example/v1/chat/completions"),
    )


def json_response(payload: dict[str, Any], status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=payload,
        request=httpx.Request("POST", "http://relay.example/v1/chat/completions"),
    )


@pytest.mark.anyio
async def test_llm_client_routes_models_by_task_type() -> None:
    fake_http = FakeHTTPClient([chat_response("a"), chat_response("b"), chat_response("c")])
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    await client.complete("screen", task_type="screening")
    await client.complete("summarize", task_type="summarization")
    await client.complete("report", task_type="weekly_report")

    assert fake_http.calls[0]["json"]["model"] == "cheap-model"
    assert fake_http.calls[1]["json"]["model"] == "standard-model"
    assert fake_http.calls[2]["json"]["model"] == "strong-model"


@pytest.mark.anyio
async def test_llm_client_routes_max_tokens_by_task_type() -> None:
    fake_http = FakeHTTPClient(
        [
            chat_response("screen"),
            chat_response("tag"),
            chat_response("summary"),
            chat_response("rank"),
            chat_response("weekly"),
            chat_response("deep"),
            chat_response("unknown"),
        ]
    )
    client = ExternalLLMClient(
        settings=make_settings(
            max_tokens=1111,
            max_tokens_cheap=2222,
            max_tokens_standard=3333,
            max_tokens_strong=4444,
        ),
        http_client=fake_http,
    )

    await client.complete("screen", task_type="screening")
    await client.complete("tag", task_type="tagging")
    await client.complete("summary", task_type="summarization")
    await client.complete("rank", task_type="ranking")
    await client.complete("weekly", task_type="weekly_report")
    await client.complete("deep", task_type="deep_analysis")
    await client.complete("unknown", task_type="unknown_task")

    assert [call["json"]["max_tokens"] for call in fake_http.calls] == [
        2222,
        2222,
        3333,
        3333,
        4444,
        4444,
        1111,
    ]


@pytest.mark.anyio
async def test_llm_client_missing_api_key_does_not_call_http() -> None:
    fake_http = FakeHTTPClient([chat_response("unused")])
    client = ExternalLLMClient(settings=make_settings(api_key=""), http_client=fake_http)

    with pytest.raises(MissingLLMConfigError, match="LLM_API_KEY"):
        await client.complete("hello")

    assert fake_http.calls == []


@pytest.mark.anyio
async def test_llm_client_parses_successful_chat_completion() -> None:
    fake_http = FakeHTTPClient([chat_response("hello from glm")])
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete(
        "Summarize this paper.",
        task_type="summarization",
        system_prompt="You summarize papers.",
        temperature=0.1,
        max_tokens=256,
    )

    assert result == "hello from glm"
    call = fake_http.calls[0]
    assert call["url"] == "http://relay.example/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer test-api-key"
    assert call["json"]["messages"] == [
        {"role": "system", "content": "You summarize papers."},
        {"role": "user", "content": "Summarize this paper."},
    ]
    assert call["json"]["temperature"] == 0.1
    assert call["json"]["max_tokens"] == 256
    assert set(call["json"].keys()) == {"model", "messages", "temperature", "max_tokens"}


@pytest.mark.anyio
async def test_llm_client_includes_configured_max_tokens_by_default() -> None:
    fake_http = FakeHTTPClient([chat_response("hello")])
    client = ExternalLLMClient(settings=make_settings(max_tokens_standard=1234), http_client=fake_http)

    await client.complete("hello")

    assert fake_http.calls[0]["json"]["max_tokens"] == 1234


@pytest.mark.anyio
async def test_llm_client_parses_list_content_parts() -> None:
    fake_http = FakeHTTPClient(
        [
            chat_response(
                [
                    {"type": "text", "text": "hello "},
                    {"type": "text", "text": "from parts"},
                ]
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("hello")

    assert result == "hello from parts"


@pytest.mark.anyio
async def test_llm_client_parses_dict_content_with_text_field() -> None:
    fake_http = FakeHTTPClient([chat_response({"text": "hello from dict"})])
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("hello")

    assert result == "hello from dict"


@pytest.mark.anyio
async def test_llm_client_does_not_return_reasoning_content_as_output() -> None:
    secret_reasoning = "SECRET GLM REASONING TRACE"
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "reasoning_content": secret_reasoning,
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(InvalidLLMResponseError, match="could not be parsed as text") as exc_info:
        await client.complete("hello")

    error_message = str(exc_info.value)
    assert secret_reasoning not in error_message
    assert "reasoning_content" not in error_message

@pytest.mark.anyio
async def test_llm_client_truncated_length_response_raises_clear_sanitized_error() -> None:
    secret_prompt = "SECRET USER PROMPT"
    secret_reasoning = "SECRET GLM REASONING TRACE"
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": None,
                                "reasoning": secret_reasoning,
                            },
                            "finish_reason": "length",
                        }
                    ]
                }
            ),
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(TruncatedLLMResponseError, match="Increase LLM_MAX_TOKENS") as exc_info:
        await client.complete(secret_prompt)

    error_message = str(exc_info.value)
    assert "LLM response was truncated before final content was produced. Increase LLM_MAX_TOKENS." in error_message
    assert "finish_reason" in error_message
    assert "content_type" in error_message
    assert secret_reasoning not in error_message
    assert "reasoning" not in error_message
    assert secret_prompt not in error_message
    assert "test-api-key" not in error_message
    assert len(fake_http.calls) == 1

@pytest.mark.anyio
async def test_llm_client_truncated_length_response_raises_for_empty_string_content() -> None:
    secret_reasoning = "SECRET GLM REASONING TRACE"
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "",
                                "reasoning": secret_reasoning,
                            },
                            "finish_reason": "length",
                        }
                    ]
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(TruncatedLLMResponseError, match="Increase LLM_MAX_TOKENS") as exc_info:
        await client.complete("hello")

    error_message = str(exc_info.value)
    assert secret_reasoning not in error_message


@pytest.mark.anyio
async def test_llm_client_truncated_length_response_raises_for_empty_list_content() -> None:
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "choices": [
                        {
                            "message": {
                                "content": [],
                            },
                            "finish_reason": "length",
                        }
                    ]
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(TruncatedLLMResponseError):
        await client.complete("hello")


@pytest.mark.anyio
async def test_llm_client_parses_choice_text_fallback() -> None:
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "choices": [
                        {
                            "text": "hello from choice text",
                            "finish_reason": "stop",
                        }
                    ]
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("hello")

    assert result == "hello from choice text"


@pytest.mark.anyio
async def test_llm_client_parses_output_text_fallback() -> None:
    fake_http = FakeHTTPClient([json_response({"output_text": "hello from output text"})])
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("hello")

    assert result == "hello from output text"


@pytest.mark.anyio
async def test_llm_client_parses_list_of_string_content_parts() -> None:
    fake_http = FakeHTTPClient([chat_response(["hello ", "from string parts"])])
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("hello")

    assert result == "hello from string parts"


@pytest.mark.anyio
async def test_llm_client_invalid_non_text_content_still_raises() -> None:
    raw_generated_text = "SECRET RAW GENERATED TEXT"
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "id": "chatcmpl-test",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": {"image_url": "https://example.com/image.png", "raw": raw_generated_text},
                            },
                            "finish_reason": "stop",
                        }
                    ],
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(InvalidLLMResponseError, match="could not be parsed as text") as exc_info:
        await client.complete("hello")

    error_message = str(exc_info.value)
    assert "top_level_keys" in error_message
    assert "choice_keys" in error_message
    assert "message_keys" in error_message
    assert "content_type" in error_message
    assert "finish_reason" in error_message
    assert "test-api-key" not in error_message
    assert "Authorization" not in error_message
    assert "image_url" not in error_message
    assert raw_generated_text not in error_message


@pytest.mark.anyio
async def test_llm_client_error_object_raises_sanitized_error() -> None:
    secret_key = "super-secret-test-key"
    raw_error_text = "upstream leaked raw provider details"
    fake_http = FakeHTTPClient(
        [
            json_response(
                {
                    "error": {
                        "message": raw_error_text,
                        "type": "relay_error",
                    }
                }
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(api_key=secret_key), http_client=fake_http)

    with pytest.raises(LLMClientError, match="error object") as exc_info:
        await client.complete("hello")

    error_message = str(exc_info.value)
    assert "top_level_keys" in error_message
    assert secret_key not in error_message
    assert raw_error_text not in error_message


@pytest.mark.anyio
async def test_llm_client_provider_max_tokens_too_large_error_retries_fallbacks() -> None:
    fake_http = FakeHTTPClient(
        [
            json_response(
                {"error": {"message": "max_tokens is too large for this model"}},
                status_code=400,
            ),
            json_response(
                {"error": {"message": "max_tokens exceeds the model limit"}},
                status_code=400,
            ),
            json_response(
                {"error": {"message": "max_tokens must be less than or equal to the token limit"}},
                status_code=400,
            ),
            chat_response("fallback worked"),
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("deep report", task_type="deep_analysis")

    assert result == "fallback worked"
    assert [call["json"]["max_tokens"] for call in fake_http.calls] == [16384, 8192, 4096, 2048]


@pytest.mark.anyio
async def test_llm_client_provider_max_tokens_too_large_error_object_retries() -> None:
    fake_http = FakeHTTPClient(
        [
            json_response({"error": {"message": "max_tokens too large"}}, status_code=200),
            chat_response("fallback worked"),
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    result = await client.complete("summary")

    assert result == "fallback worked"
    assert [call["json"]["max_tokens"] for call in fake_http.calls] == [8192, 4096]


@pytest.mark.anyio
async def test_llm_client_provider_max_tokens_too_large_failure_is_sanitized(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_key = "super-secret-test-key"
    raw_error_text = "max_tokens too large; raw provider trace SECRET DETAILS"
    fake_http = FakeHTTPClient(
        [
            json_response({"error": {"message": raw_error_text}}, status_code=400),
            json_response({"error": {"message": raw_error_text}}, status_code=400),
            json_response({"error": {"message": raw_error_text}}, status_code=400),
            json_response({"error": {"message": raw_error_text}}, status_code=400),
        ]
    )
    client = ExternalLLMClient(settings=make_settings(api_key=secret_key), http_client=fake_http)

    with pytest.raises(LLMClientError, match="fallback retries") as exc_info:
        await client.complete("deep report", task_type="deep_analysis")

    assert [call["json"]["max_tokens"] for call in fake_http.calls] == [16384, 8192, 4096, 2048]
    error_message = str(exc_info.value)
    assert raw_error_text not in error_message
    assert secret_key not in error_message
    assert raw_error_text not in caplog.text
    assert secret_key not in caplog.text


@pytest.mark.anyio
async def test_llm_client_retries_transient_failure() -> None:
    fake_http = FakeHTTPClient(
        [
            httpx.TimeoutException("temporary timeout"),
            chat_response("retry worked"),
        ]
    )
    client = ExternalLLMClient(settings=make_settings(max_retries=2), http_client=fake_http)

    result = await client.complete("try again", task_type="ranking")

    assert result == "retry worked"
    assert len(fake_http.calls) == 2


@pytest.mark.anyio
async def test_llm_client_invalid_response_format() -> None:
    fake_http = FakeHTTPClient(
        [
            httpx.Response(
                status_code=200,
                json={"choices": []},
                request=httpx.Request("POST", "http://relay.example/v1/chat/completions"),
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(), http_client=fake_http)

    with pytest.raises(InvalidLLMResponseError, match="could not be parsed as text"):
        await client.complete("bad shape")


@pytest.mark.anyio
async def test_llm_client_does_not_leak_api_key_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    secret_key = "super-secret-test-key"
    fake_http = FakeHTTPClient(
        [
            httpx.Response(
                status_code=500,
                json={"error": {"message": "upstream failed"}},
                request=httpx.Request("POST", "http://relay.example/v1/chat/completions"),
            )
        ]
    )
    client = ExternalLLMClient(settings=make_settings(api_key=secret_key, max_retries=1), http_client=fake_http)

    with pytest.raises(LLMClientError) as exc_info:
        await client.complete("will fail", task_type="deep_analysis")

    assert secret_key not in str(exc_info.value)
    assert secret_key not in caplog.text
