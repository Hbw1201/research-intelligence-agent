from backend.collectors.rss_discovery import discover_feed_urls


def test_rss_discovery_extracts_alternate_feed_links_and_common_candidates() -> None:
    html = """
    <html>
      <head>
        <link rel="alternate" type="application/rss+xml" href="/rss.xml">
        <link rel="alternate" type="application/atom+xml" href="https://feeds.example.com/atom">
      </head>
    </html>
    """

    urls = discover_feed_urls("https://example.com/articles/page", html)

    assert "https://example.com/rss.xml" in urls
    assert "https://feeds.example.com/atom" in urls
    assert "https://example.com/rss" in urls
    assert "https://example.com/feed" in urls
    assert "https://example.com/atom.xml" in urls
