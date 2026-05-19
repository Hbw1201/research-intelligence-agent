"""Search clients for web discovery."""

from backend.search.search_result import SearchResult
from backend.search.searxng_client import SearxNGClient
from backend.search.web_search_client import WebSearchClient

__all__ = [
    "SearchResult",
    "SearxNGClient",
    "WebSearchClient",
]
