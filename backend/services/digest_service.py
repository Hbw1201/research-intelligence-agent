from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.collectors.base import ResearchItem
from backend.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是一个谨慎、克制的科研情报摘要助手。"
    "请用中文输出，避免夸大结论；当摘要或元数据不足时，明确说明不确定性。"
)


class DigestItem(BaseModel):
    """Chinese research intelligence summary for a normalized item."""

    title: str
    item_type: str
    source_name: str
    url: str
    one_sentence_summary: str
    key_points: list[str] = Field(default_factory=list)
    relevance_reason: str
    recommended_action: str
    importance_level: Literal["low", "medium", "high"] = "medium"


class DigestParseError(ValueError):
    """Raised when an LLM digest response cannot be parsed as a DigestItem."""


class ChineseDigestService:
    """Generate Chinese research intelligence digests from collected items."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def summarize_item(self, item: ResearchItem, user_profile: str | None = None) -> DigestItem:
        """Summarize one research item using the configured LLM client."""
        prompt = self._build_prompt(item, user_profile)
        response = await self.llm_client.complete(
            prompt,
            task_type="summarization",
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        try:
            return self._parse_digest_response(response, item)
        except DigestParseError:
            logger.warning(
                "LLM digest response was malformed; using safe fallback for source=%s item_type=%s",
                item.source_name,
                item.item_type,
            )
            return self._fallback_digest(item, user_profile)

    async def summarize_items(
        self,
        items: list[ResearchItem],
        user_profile: str | None = None,
        max_items: int = 10,
    ) -> list[DigestItem]:
        """Summarize up to max_items research items."""
        if max_items <= 0:
            return []

        digests: list[DigestItem] = []
        for item in items[:max_items]:
            digests.append(await self.summarize_item(item, user_profile=user_profile))
        return digests

    def format_daily_digest(self, digests: list[DigestItem], title: str = "今日科研情报") -> str:
        """Format digest items in a WeChat-friendly text form."""
        if not digests:
            return f"# {title}\n\n暂无新的科研情报。"

        lines = [f"# {title}", "", f"共 {len(digests)} 条"]
        for index, digest in enumerate(digests, start=1):
            lines.extend(
                [
                    "",
                    f"{index}. **{digest.title}**",
                    f"来源：{digest.source_name} | 类型：{digest.item_type} | 重要性：{digest.importance_level}",
                    f"一句话：{digest.one_sentence_summary}",
                ]
            )
            if digest.key_points:
                lines.append("要点：")
                lines.extend(f"- {point}" for point in digest.key_points[:5])
            lines.extend(
                [
                    f"相关性：{digest.relevance_reason}",
                    f"建议：{digest.recommended_action}",
                    f"链接：{digest.url}",
                ]
            )
        return "\n".join(lines)

    async def generate(self, items: list[ResearchItem]) -> str:
        """Compatibility helper for the earlier placeholder service API."""
        digests = await self.summarize_items(items)
        return self.format_daily_digest(digests)

    @classmethod
    def _build_prompt(cls, item: ResearchItem, user_profile: str | None) -> str:
        item_payload = {
            "title": item.title,
            "abstract": cls._truncate_text(item.abstract, 1800),
            "url": item.url,
            "source_name": item.source_name,
            "source_type": item.source_type,
            "item_type": item.item_type,
            "authors": item.authors,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "external_id": item.external_id,
            "keywords": item.keywords,
            "metadata": item.metadata,
            "raw_text": cls._truncate_text(item.raw_text, 1200),
        }
        item_json = json.dumps(item_payload, ensure_ascii=False, default=str, indent=2)
        profile = user_profile.strip() if user_profile else "未提供用户画像"

        return (
            "请根据以下科研条目生成中文科研情报摘要。\n"
            "输出必须是严格 JSON 对象，不要使用 Markdown 代码块，不要添加 JSON 以外的解释。\n"
            "JSON 必须包含这些字段：title, item_type, source_name, url, one_sentence_summary, "
            "key_points, relevance_reason, recommended_action, importance_level。\n"
            "importance_level 只能是 low、medium、high 之一。\n"
            "要求：\n"
            "- 用中文表达，适合微信群/企业微信阅读。\n"
            "- 避免夸大贡献，不要把未经验证的发现说成确定结论。\n"
            "- 如果摘要、README 或元数据不足，请在摘要或相关性中说明不确定性。\n"
            "- relevance_reason 需要解释它为什么可能符合用户画像。\n"
            "- recommended_action 给出一个简短、可执行的下一步。\n\n"
            f"用户画像：{profile}\n\n"
            f"科研条目 JSON：\n{item_json}"
        )

    @classmethod
    def _parse_digest_response(cls, response: str, item: ResearchItem) -> DigestItem:
        try:
            data = json.loads(cls._extract_json_object(response))
        except json.JSONDecodeError as exc:
            raise DigestParseError("LLM digest response is not valid JSON.") from exc

        if not isinstance(data, dict):
            raise DigestParseError("LLM digest response JSON is not an object.")

        if isinstance(data.get("key_points"), str):
            data["key_points"] = [data["key_points"]]

        normalized = {
            **data,
            "title": item.title,
            "item_type": item.item_type,
            "source_name": item.source_name,
            "url": item.url,
        }
        try:
            return DigestItem.model_validate(normalized)
        except ValidationError as exc:
            raise DigestParseError("LLM digest response does not match DigestItem schema.") from exc

    @staticmethod
    def _extract_json_object(response: str) -> str:
        text = response.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
        if fenced:
            text = fenced.group(1).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise DigestParseError("LLM digest response does not contain a JSON object.")
        return text[start : end + 1]

    @classmethod
    def _fallback_digest(cls, item: ResearchItem, user_profile: str | None) -> DigestItem:
        abstract = cls._truncate_text(item.abstract or item.raw_text, 180)
        has_context = bool(abstract)
        if has_context:
            summary = f"基于现有信息，该条目可能涉及：{abstract}"
        else:
            summary = "该条目缺少足够的摘要或元数据，暂无法可靠判断具体贡献。"

        key_points = cls._fallback_key_points(item, abstract)
        if user_profile:
            profile = cls._truncate_text(user_profile, 80)
            relevance = f"可能与用户画像（{profile}）相关，但当前证据有限，需要进一步阅读原文确认。"
        else:
            relevance = "未提供用户画像，相关性需要结合具体研究方向进一步判断。"

        action = "优先阅读摘要、方法和实验设置，再决定是否纳入周报。" if has_context else "先打开链接确认主题、摘要和来源可信度。"
        return DigestItem(
            title=item.title,
            item_type=item.item_type,
            source_name=item.source_name,
            url=item.url,
            one_sentence_summary=summary,
            key_points=key_points,
            relevance_reason=relevance,
            recommended_action=action,
            importance_level="medium" if has_context else "low",
        )

    @classmethod
    def _fallback_key_points(cls, item: ResearchItem, abstract: str) -> list[str]:
        points: list[str] = []
        if abstract:
            points.append(f"可用摘要片段：{abstract}")
        if item.authors:
            points.append(f"作者/维护者：{', '.join(item.authors[:3])}")
        if item.keywords:
            points.append(f"关键词：{', '.join(item.keywords[:5])}")
        if not points:
            points.append("元数据不足，建议打开原文确认。")
        return points

    @staticmethod
    def _truncate_text(text: str | None, max_chars: int) -> str:
        if not text:
            return ""
        normalized = " ".join(text.split())
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 3].rstrip() + "..."
