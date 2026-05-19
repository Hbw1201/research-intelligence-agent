from __future__ import annotations

from datetime import datetime, timezone

from backend.services.digest_service import DigestItem
from backend.services.html_report_renderer import HtmlReportMetadata, HtmlReportRenderer


def test_html_renderer_converts_markdown_report_to_safe_html() -> None:
    renderer = HtmlReportRenderer()
    digest = DigestItem(
        title="Safe digest",
        item_type="paper",
        source_name="arxiv",
        url="https://example.com/paper",
        one_sentence_summary="Useful update.",
        key_points=["First point"],
        relevance_reason="Matches the topic.",
        recommended_action="Read it.",
        importance_level="medium",
    )

    html = renderer.render(
        title="Daily <Report>",
        markdown_report="# Title\n\n<script>alert(1)</script>\n\n- **Point** [link](javascript:alert(1))",
        digests=[digest],
        metadata=HtmlReportMetadata(
            generated_at=datetime(2026, 5, 19, 8, 30, tzinfo=timezone.utc),
            sources=["web"],
            keywords=["single-cell"],
            warnings=["web: warning"],
            dedup_summary={"collected_items": 3, "duplicates_skipped": 1, "new_items_included": 2},
        ),
    )

    assert "<!doctype html>" in html
    assert "&lt;Report&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'href="#"' in html
    assert "<strong>Point</strong>" in html
    assert "Safe digest" in html
    assert "Collected items" in html
