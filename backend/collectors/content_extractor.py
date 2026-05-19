from __future__ import annotations

from html.parser import HTMLParser
import re


class ContentExtractionResult:
    """Readable content extracted from a fetched web page."""

    def __init__(self, title: str | None, text: str) -> None:
        self.title = title
        self.text = text


class ContentExtractor:
    """Small standard-library HTML/text extractor for MVP web discovery."""

    def extract(self, content: str, content_type: str | None = None) -> ContentExtractionResult:
        """Extract a title and readable text from HTML or plain text."""
        if self._is_plain_text(content_type):
            text = self._normalize_text(content)
            return ContentExtractionResult(title=None, text=text)

        parser = _ReadableHTMLParser()
        parser.feed(content)
        return ContentExtractionResult(
            title=self._normalize_text(parser.title) or None,
            text=self._normalize_text(" ".join(parser.text_parts)),
        )

    @staticmethod
    def _is_plain_text(content_type: str | None) -> bool:
        return bool(content_type and "text/plain" in content_type.lower())

    @staticmethod
    def _normalize_text(value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip()


class _ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.text_parts: list[str] = []
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        self._tag_stack.append(tag.lower())

    def handle_endtag(self, tag: str) -> None:
        normalized = tag.lower()
        for index in range(len(self._tag_stack) - 1, -1, -1):
            if self._tag_stack[index] == normalized:
                del self._tag_stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self._is_ignored_context():
            return
        text = data.strip()
        if not text:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self.title = f"{self.title} {text}".strip()
            return
        self.text_parts.append(text)

    def _is_ignored_context(self) -> bool:
        ignored_tags = {"script", "style", "nav", "noscript", "svg"}
        return any(tag in ignored_tags for tag in self._tag_stack)
