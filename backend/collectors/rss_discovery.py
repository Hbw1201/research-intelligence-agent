from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


RSS_MIME_TYPES = {"application/rss+xml", "application/atom+xml"}
COMMON_FEED_PATHS = ("/rss", "/feed", "/atom.xml")


def discover_feed_urls(page_url: str, html: str) -> list[str]:
    """Discover likely RSS/Atom feed URLs without fetching candidates."""
    parser = _FeedLinkParser()
    parser.feed(html)

    urls: list[str] = []
    seen: set[str] = set()
    for href in [*parser.hrefs, *COMMON_FEED_PATHS]:
        absolute_url = urljoin(page_url, href)
        if absolute_url not in seen:
            seen.add(absolute_url)
            urls.append(absolute_url)
    return urls


class _FeedLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return

        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        rel = attr_map.get("rel", "").lower()
        mime_type = attr_map.get("type", "").lower()
        href = attr_map.get("href", "")
        if "alternate" in rel and mime_type in RSS_MIME_TYPES and href:
            self.hrefs.append(href)
