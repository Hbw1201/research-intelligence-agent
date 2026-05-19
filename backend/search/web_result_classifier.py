from __future__ import annotations

import re
from urllib.parse import urlparse

from backend.search.search_result import SearchResult


PAPER_DOMAINS = {
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
}

DATASET_DOMAINS = {
    "kaggle.com",
    "zenodo.org",
    "figshare.com",
    "dataverse.harvard.edu",
    "dryad.org",
}

COMPANY_RESEARCH_DOMAINS = {
    "research.google",
    "deepmind.google",
    "openai.com",
    "ai.meta.com",
    "microsoft.com",
    "research.microsoft.com",
    "anthropic.com",
    "nvidia.com",
}

LAB_DOMAIN_PARTS = {
    ".edu",
    ".ac.",
    "university",
    "mit.edu",
    "stanford.edu",
    "harvard.edu",
    "berkeley.edu",
    "cmu.edu",
}


class WebResultClassifier:
    """Rule-based MVP classifier for broad web-discovery results."""

    def classify(self, result: SearchResult) -> str:
        """Classify a web search result into the MVP item_type taxonomy."""
        url = result.url
        title = result.title
        snippet = result.snippet
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.lower()
        text = f"{title} {snippet} {path}".lower()

        if self._matches_domain(host, {"github.com", "gitlab.com", "bitbucket.org"}):
            return "code"
        if self._is_paper(host, path):
            return "paper"
        if self._is_dataset(host, path, text):
            return "dataset"
        if self._has_any(text, {"benchmark", "leaderboard", "evaluation", "eval", "testbed"}):
            return "benchmark"
        if self._is_company_research(host, path, text):
            return "company_research"
        if self._is_news(path, text):
            return "news"
        if self._is_blog(path, text):
            return "blog"
        if self._is_lab_page(host, path, text):
            return "lab_page"
        return "webpage"

    def source_type_for_item_type(self, item_type: str) -> str:
        """Map item_type into the coarser ResearchItem source_type field."""
        if item_type == "paper":
            return "paper"
        if item_type == "code":
            return "code"
        if item_type == "dataset":
            return "dataset"
        if item_type in {"news", "blog", "lab_page", "company_research"}:
            return "news"
        if item_type == "benchmark":
            return "benchmark"
        return "web"

    def _is_paper(self, host: str, path: str) -> bool:
        if self._matches_domain(host, PAPER_DOMAINS):
            return True
        return self._matches_domain(host, {"nature.com"}) and path.startswith("/articles")

    def _is_dataset(self, host: str, path: str, text: str) -> bool:
        if self._matches_domain(host, DATASET_DOMAINS):
            return True
        if self._matches_domain(host, {"huggingface.co"}) and path.startswith("/datasets"):
            return True
        return self._has_any(text, {"dataset", "data repository", "benchmark dataset"})

    def _is_company_research(self, host: str, path: str, text: str) -> bool:
        if not self._matches_domain(host, COMPANY_RESEARCH_DOMAINS):
            return False
        return "/research" in path or "research" in text or "blog" in path

    def _is_news(self, path: str, text: str) -> bool:
        return "/news" in path or self._has_any(text, {"news release", "press release", "announcement"})

    def _is_blog(self, path: str, text: str) -> bool:
        return "/blog" in path or "/posts" in path or self._has_any(text, {"blog", "technical update"})

    def _is_lab_page(self, host: str, path: str, text: str) -> bool:
        return (
            any(part in host for part in LAB_DOMAIN_PARTS)
            and ("/lab" in path or "/group" in path or self._has_any(text, {"lab", "laboratory", "research group"}))
        )

    @staticmethod
    def _matches_domain(host: str, domains: set[str]) -> bool:
        return any(host == domain or host.endswith(f".{domain}") for domain in domains)

    @staticmethod
    def _has_any(text: str, words: set[str]) -> bool:
        return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


__all__ = ["WebResultClassifier"]
