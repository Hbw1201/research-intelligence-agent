from __future__ import annotations

import html
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from backend.collectors.base import ResearchItem
from backend.services.digest_service import DigestItem


@dataclass(frozen=True)
class HtmlReportMetadata:
    """Metadata displayed near the top of a static HTML report."""

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sources: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dedup_summary: Mapping[str, Any] | None = None


class HtmlReportRenderer:
    """Render a self-contained, mobile-friendly HTML report from markdown."""

    def render(
        self,
        title: str,
        markdown_report: str,
        digests: list[DigestItem] | None = None,
        items: list[ResearchItem] | None = None,
        metadata: HtmlReportMetadata | Mapping[str, Any] | None = None,
    ) -> str:
        """Return a complete static HTML document with embedded CSS."""
        normalized_metadata = self._normalize_metadata(metadata)
        safe_title = html.escape(title.strip() or "Daily Research Intelligence")
        generated_at = normalized_metadata.generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        body_sections = [
            self._render_header(safe_title, generated_at, normalized_metadata),
            self._render_digest_cards(digests or []),
            self._render_markdown(markdown_report),
            self._render_item_links(items or []),
        ]
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="zh-CN">',
                "<head>",
                '  <meta charset="utf-8">',
                '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                f"  <title>{safe_title}</title>",
                f"  <style>{self._css()}</style>",
                "</head>",
                "<body>",
                '  <main class="page">',
                *[section for section in body_sections if section],
                "  </main>",
                "</body>",
                "</html>",
            ]
        )

    def _render_header(self, safe_title: str, generated_at: str, metadata: HtmlReportMetadata) -> str:
        chips = []
        if metadata.keywords:
            chips.append(("Keywords", ", ".join(metadata.keywords)))
        if metadata.sources:
            chips.append(("Sources", ", ".join(metadata.sources)))
        chips.append(("Generated", generated_at))

        chip_html = "\n".join(
            f'<span class="chip"><strong>{html.escape(label)}</strong>{html.escape(value)}</span>'
            for label, value in chips
        )
        warning_html = ""
        if metadata.warnings:
            warning_items = "\n".join(f"<li>{html.escape(warning)}</li>" for warning in metadata.warnings)
            warning_html = f'<section class="notice"><h2>Warnings</h2><ul>{warning_items}</ul></section>'

        dedup_html = self._render_dedup_summary(metadata.dedup_summary)
        return "\n".join(
            [
                '    <header class="report-header">',
                f"      <h1>{safe_title}</h1>",
                f'      <div class="meta">{chip_html}</div>',
                "    </header>",
                warning_html,
                dedup_html,
            ]
        )

    @staticmethod
    def _render_dedup_summary(summary: Mapping[str, Any] | None) -> str:
        if not summary:
            return ""
        labels = {
            "collected_items": "Collected items",
            "duplicates_skipped": "Duplicates skipped",
            "new_items_included": "New items included",
        }
        rows = []
        for key, label in labels.items():
            if key in summary:
                rows.append(
                    f'<span class="stat"><strong>{html.escape(str(summary[key]))}</strong>{html.escape(label)}</span>'
                )
        if not rows:
            return ""
        return f'<section class="stats">{"".join(rows)}</section>'

    def _render_digest_cards(self, digests: list[DigestItem]) -> str:
        if not digests:
            return ""
        cards = []
        for index, digest in enumerate(digests, start=1):
            points = "".join(f"<li>{self._inline(point)}</li>" for point in digest.key_points[:5])
            points_html = f"<ul>{points}</ul>" if points else ""
            cards.append(
                "\n".join(
                    [
                        '<article class="digest-card">',
                        f'  <div class="card-kicker">#{index} · {html.escape(digest.source_name)} · {html.escape(digest.item_type)}</div>',
                        f"  <h2>{html.escape(digest.title)}</h2>",
                        f'  <p class="summary">{self._inline(digest.one_sentence_summary)}</p>',
                        points_html,
                        f'  <p><strong>Why it matters:</strong> {self._inline(digest.relevance_reason)}</p>',
                        f'  <p><strong>Next step:</strong> {self._inline(digest.recommended_action)}</p>',
                        f'  <p><a href="{self._safe_href(digest.url)}" rel="noopener noreferrer">Open source</a></p>',
                        "</article>",
                    ]
                )
            )
        return '<section class="digest-grid">\n' + "\n".join(cards) + "\n</section>"

    def _render_item_links(self, items: list[ResearchItem]) -> str:
        if not items:
            return ""
        rows = []
        for item in items:
            rows.append(
                "\n".join(
                    [
                        "<li>",
                        f'<a href="{self._safe_href(item.url)}" rel="noopener noreferrer">{html.escape(item.title)}</a>',
                        f'<span>{html.escape(item.source_name)} · {html.escape(item.item_type)}</span>',
                        "</li>",
                    ]
                )
            )
        return '<section class="source-links"><h2>Source links</h2><ul>' + "\n".join(rows) + "</ul></section>"

    def _render_markdown(self, markdown_report: str) -> str:
        lines = markdown_report.splitlines()
        rendered: list[str] = ['<section class="markdown-report">']
        list_mode: str | None = None

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                if list_mode:
                    rendered.append(f"</{list_mode}>")
                    list_mode = None
                continue

            heading_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
            if heading_match:
                if list_mode:
                    rendered.append(f"</{list_mode}>")
                    list_mode = None
                level = min(len(heading_match.group(1)) + 1, 5)
                rendered.append(f"<h{level}>{self._inline(heading_match.group(2))}</h{level}>")
                continue

            unordered_match = re.match(r"^[-*]\s+(.+)$", stripped)
            if unordered_match:
                if list_mode != "ul":
                    if list_mode:
                        rendered.append(f"</{list_mode}>")
                    rendered.append("<ul>")
                    list_mode = "ul"
                rendered.append(f"<li>{self._inline(unordered_match.group(1))}</li>")
                continue

            ordered_match = re.match(r"^\d+\.\s+(.+)$", stripped)
            if ordered_match:
                if list_mode != "ol":
                    if list_mode:
                        rendered.append(f"</{list_mode}>")
                    rendered.append("<ol>")
                    list_mode = "ol"
                rendered.append(f"<li>{self._inline(ordered_match.group(1))}</li>")
                continue

            if list_mode:
                rendered.append(f"</{list_mode}>")
                list_mode = None
            rendered.append(f"<p>{self._inline(stripped)}</p>")

        if list_mode:
            rendered.append(f"</{list_mode}>")
        rendered.append("</section>")
        return "\n".join(rendered)

    def _inline(self, text: str) -> str:
        link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        output: list[str] = []
        last_end = 0
        for match in link_pattern.finditer(text):
            output.append(self._emphasis(html.escape(text[last_end : match.start()])))
            label = self._emphasis(html.escape(match.group(1)))
            href = self._safe_href(match.group(2))
            output.append(f'<a href="{href}" rel="noopener noreferrer">{label}</a>')
            last_end = match.end()
        output.append(self._emphasis(html.escape(text[last_end:])))
        return "".join(output)

    @staticmethod
    def _emphasis(escaped_text: str) -> str:
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped_text)

    @staticmethod
    def _safe_href(url: str) -> str:
        parsed = urlparse(str(url).strip())
        if parsed.scheme.lower() not in {"http", "https", "mailto"}:
            return "#"
        return html.escape(str(url).strip(), quote=True)

    @staticmethod
    def _normalize_metadata(metadata: HtmlReportMetadata | Mapping[str, Any] | None) -> HtmlReportMetadata:
        if isinstance(metadata, HtmlReportMetadata):
            return metadata
        if not metadata:
            return HtmlReportMetadata()
        generated_at = metadata.get("generated_at") or datetime.now(timezone.utc)
        if isinstance(generated_at, str):
            try:
                generated_at = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError:
                generated_at = datetime.now(timezone.utc)
        if not isinstance(generated_at, datetime):
            generated_at = datetime.now(timezone.utc)
        return HtmlReportMetadata(
            generated_at=generated_at,
            sources=[str(value) for value in metadata.get("sources", [])],
            keywords=[str(value) for value in metadata.get("keywords", [])],
            warnings=[str(value) for value in metadata.get("warnings", [])],
            dedup_summary=metadata.get("dedup_summary"),
        )

    @staticmethod
    def _css() -> str:
        return """
:root {
  color-scheme: light;
  --bg: #f7f9fb;
  --panel: #ffffff;
  --text: #17202a;
  --muted: #5d6b7a;
  --border: #d9e1ea;
  --accent: #145ea8;
  --accent-soft: #e7f1fb;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, "Noto Sans SC", sans-serif;
}
a { color: var(--accent); overflow-wrap: anywhere; }
.page {
  width: min(1080px, 100%);
  margin: 0 auto;
  padding: 28px 18px 56px;
}
.report-header {
  padding: 28px 0 18px;
  border-bottom: 1px solid var(--border);
}
.report-header h1 {
  margin: 0 0 16px;
  font-size: clamp(1.8rem, 4vw, 2.6rem);
  line-height: 1.18;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip, .stat {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 8px;
  padding: 6px 10px;
  color: var(--muted);
  font-size: 0.92rem;
}
.chip strong, .stat strong { color: var(--text); }
.stats {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 18px 0;
}
.stat {
  min-width: 150px;
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
}
.stat strong { font-size: 1.35rem; }
.notice, .digest-card, .markdown-report, .source-links {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px;
  margin: 18px 0;
}
.notice { background: #fff8e6; }
.digest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  margin: 20px 0;
}
.digest-card { margin: 0; }
.digest-card h2, .markdown-report h2, .source-links h2 {
  margin-top: 0;
  line-height: 1.25;
}
.card-kicker {
  color: var(--muted);
  font-size: 0.85rem;
  margin-bottom: 8px;
}
.summary {
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  padding: 10px 12px;
}
.markdown-report h2, .markdown-report h3, .markdown-report h4, .markdown-report h5 {
  margin-top: 1.25em;
}
.markdown-report p, .markdown-report li {
  overflow-wrap: anywhere;
}
.source-links ul {
  list-style: none;
  padding: 0;
}
.source-links li {
  display: grid;
  gap: 2px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.source-links li:last-child { border-bottom: 0; }
.source-links span { color: var(--muted); font-size: 0.9rem; }
@media (max-width: 640px) {
  .page { padding: 18px 12px 40px; }
  .notice, .digest-card, .markdown-report, .source-links { padding: 14px; }
}
""".strip()


__all__ = ["HtmlReportMetadata", "HtmlReportRenderer"]
