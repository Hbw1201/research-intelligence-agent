import json
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.collectors.base import ResearchItem
from backend.services.digest_service import ChineseDigestService, DigestItem


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        prompt: object,
        task_type: str = "summarization",
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "prompt": prompt,
                "task_type": task_type,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.responses.pop(0)


def make_item(title: str = "Graph Agent Memory") -> ResearchItem:
    return ResearchItem(
        title=title,
        abstract="A method for memory-augmented graph agents with retrieval and evaluation.",
        url=f"https://example.com/{title.lower().replace(' ', '-')}",
        source_name="arxiv",
        source_type="paper",
        item_type="paper",
        authors=["Ada Lovelace", "Alan Turing"],
        published_at=datetime(2026, 5, 18, tzinfo=timezone.utc),
        raw_text="Graph Agent Memory\n\nA method for memory-augmented graph agents.",
        external_id="2605.00001",
        keywords=["cs.AI", "multi-agent"],
        metadata={"primary_category": "cs.AI"},
    )


def digest_json(**overrides: object) -> str:
    payload: dict[str, object] = {
        "title": "LLM title should be replaced",
        "item_type": "paper",
        "source_name": "arxiv",
        "url": "https://wrong.example",
        "one_sentence_summary": "该工作提出一种面向图智能体的记忆增强方法。",
        "key_points": ["结合检索与记忆机制", "包含实验评估"],
        "relevance_reason": "与多智能体和图学习方向相关。",
        "recommended_action": "阅读方法部分并检查实验设置。",
        "importance_level": "high",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.anyio
async def test_summarize_item_with_mocked_llm_response() -> None:
    fake_llm = FakeLLMClient([digest_json()])
    service = ChineseDigestService(fake_llm)
    item = make_item()

    digest = await service.summarize_item(item, user_profile="关注多智能体系统和图学习")

    assert digest == DigestItem(
        title=item.title,
        item_type=item.item_type,
        source_name=item.source_name,
        url=item.url,
        one_sentence_summary="该工作提出一种面向图智能体的记忆增强方法。",
        key_points=["结合检索与记忆机制", "包含实验评估"],
        relevance_reason="与多智能体和图学习方向相关。",
        recommended_action="阅读方法部分并检查实验设置。",
        importance_level="high",
    )
    assert len(fake_llm.calls) == 1
    call = fake_llm.calls[0]
    assert call["task_type"] == "summarization"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 900
    assert "关注多智能体系统和图学习" in str(call["prompt"])
    assert "严格 JSON 对象" in str(call["prompt"])


@pytest.mark.anyio
async def test_summarize_items_respects_max_items() -> None:
    fake_llm = FakeLLMClient([digest_json(), digest_json(), digest_json()])
    service = ChineseDigestService(fake_llm)
    items = [make_item(f"Paper {index}") for index in range(3)]

    digests = await service.summarize_items(items, max_items=2)

    assert len(digests) == 2
    assert [digest.title for digest in digests] == ["Paper 0", "Paper 1"]
    assert len(fake_llm.calls) == 2


def test_format_daily_digest_output() -> None:
    service = ChineseDigestService(FakeLLMClient([]))
    digest = DigestItem(
        title="Graph Agent Memory",
        item_type="paper",
        source_name="arxiv",
        url="https://example.com/paper",
        one_sentence_summary="该工作提出一种面向图智能体的记忆增强方法。",
        key_points=["结合检索与记忆机制", "包含实验评估"],
        relevance_reason="与多智能体和图学习方向相关。",
        recommended_action="阅读方法部分并检查实验设置。",
        importance_level="medium",
    )

    text = service.format_daily_digest([digest], title="今日科研情报")

    assert "# 今日科研情报" in text
    assert "共 1 条" in text
    assert "Graph Agent Memory" in text
    assert "一句话：该工作提出一种面向图智能体的记忆增强方法。" in text
    assert "重要性：medium" in text
    assert "链接：https://example.com/paper" in text


def test_format_daily_digest_empty_output() -> None:
    service = ChineseDigestService(FakeLLMClient([]))

    text = service.format_daily_digest([], title="今日科研情报")

    assert text == "# 今日科研情报\n\n暂无新的科研情报。"


@pytest.mark.anyio
async def test_summarize_item_falls_back_on_invalid_json() -> None:
    fake_llm = FakeLLMClient(["not json at all"])
    service = ChineseDigestService(fake_llm)
    item = make_item()

    digest = await service.summarize_item(item, user_profile="多智能体系统")

    assert digest.title == item.title
    assert digest.url == item.url
    assert digest.importance_level == "medium"
    assert "基于现有信息" in digest.one_sentence_summary
    assert "多智能体系统" in digest.relevance_reason
    assert len(fake_llm.calls) == 1


@pytest.mark.anyio
async def test_summarize_item_falls_back_on_malformed_content() -> None:
    fake_llm = FakeLLMClient([digest_json(importance_level="urgent")])
    service = ChineseDigestService(fake_llm)
    item = make_item()

    digest = await service.summarize_item(item)

    assert digest.title == item.title
    assert digest.importance_level == "medium"
    assert "未提供用户画像" in digest.relevance_reason
    assert len(fake_llm.calls) == 1
