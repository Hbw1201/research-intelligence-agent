from backend.collectors.content_extractor import ContentExtractor


def test_content_extractor_extracts_title_and_readable_html_text() -> None:
    html = """
    <html>
      <head><title>Single-cell Update</title><style>.x{}</style></head>
      <body>
        <nav>Navigation should be skipped</nav>
        <main><h1>Foundation model</h1><p>Readable scientific update.</p></main>
        <script>console.log("skip")</script>
      </body>
    </html>
    """

    result = ContentExtractor().extract(html, "text/html")

    assert result.title == "Single-cell Update"
    assert "Foundation model" in result.text
    assert "Readable scientific update." in result.text
    assert "Navigation should be skipped" not in result.text
    assert "console.log" not in result.text
