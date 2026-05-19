from __future__ import annotations

import re
import string
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from backend.collectors.base import ResearchItem


TRACKING_QUERY_PARAMS = {
    "campaign",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "spm",
}


def item_fingerprint(item: ResearchItem) -> str:
    """Return a stable deduplication fingerprint for a collected item."""
    doi = normalize_doi(_metadata_value(item.metadata, "doi"))
    if doi:
        return f"doi:{doi}"

    pmid = _item_pubmed_id(item)
    if pmid:
        return f"pmid:{pmid}"

    arxiv_id = _item_arxiv_id(item)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"

    github_repo = _item_github_repo(item)
    if github_repo:
        return f"github:{github_repo}"

    canonical_url = normalize_canonical_url(_metadata_value(item.metadata, "canonical_url") or item.url)
    if canonical_url:
        return f"url:{canonical_url}"

    return f"title:{normalize_title(item.title)}"


def normalize_canonical_url(url: str | None) -> str:
    """Normalize URLs for stable history-based deduplication."""
    if not url:
        return ""
    raw_url = str(url).strip()
    if not raw_url:
        return ""

    parsed = urlsplit(raw_url)
    if not parsed.scheme and not parsed.netloc:
        return raw_url.rstrip("/").lower()

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")

    if scheme in {"http", "https"}:
        scheme, netloc = _normalize_http_scheme_and_host(scheme, netloc)

    query_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query_params.sort(key=lambda pair: (pair[0].lower(), pair[1]))

    normalized = urlunsplit(
        (
            scheme,
            netloc,
            path,
            urlencode(query_params, doseq=True),
            "",
        )
    )
    return normalized.rstrip("/").lower()


def normalize_title(title: str | None) -> str:
    """Normalize a title fallback while keeping non-punctuation text intact."""
    if not title:
        return ""
    without_punctuation = "".join(" " if _is_punctuation(char) else char for char in title)
    return re.sub(r"\s+", " ", without_punctuation).strip().lower()


def normalize_doi(value: Any) -> str:
    if value is None:
        return ""
    doi = str(value).strip().lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    doi = doi.strip().strip(".;,")
    return doi


def normalize_pubmed_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    match = re.search(r"\b\d{1,12}\b", text)
    return match.group(0) if match else ""


def normalize_arxiv_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text)
    text = re.sub(r"^arxiv:", "", text)
    text = text.removesuffix(".pdf")
    text = text.rstrip("/")
    text = re.sub(r"v\d+$", "", text)
    return text


def normalize_github_repo(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""

    parsed = urlsplit(text)
    host = (parsed.hostname or "").lower()
    if host in {"github.com", "www.github.com"}:
        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2:
            return _clean_github_full_name("/".join(path_parts[:2]))

    if "/" in text and not text.startswith(("http://", "https://")):
        parts = [part for part in text.split("/") if part]
        if len(parts) >= 2:
            return _clean_github_full_name("/".join(parts[:2]))

    return ""


def _item_pubmed_id(item: ResearchItem) -> str:
    for key in ("pmid", "pubmed_id", "pubmed"):
        pmid = normalize_pubmed_id(_metadata_value(item.metadata, key))
        if pmid:
            return pmid

    if item.source_name.lower() == "pubmed":
        pmid = normalize_pubmed_id(item.external_id)
        if pmid:
            return pmid

    parsed = urlsplit(item.url)
    if (parsed.hostname or "").lower() == "pubmed.ncbi.nlm.nih.gov":
        return normalize_pubmed_id(parsed.path)
    return ""


def _item_arxiv_id(item: ResearchItem) -> str:
    for key in ("arxiv_id", "arxiv"):
        arxiv_id = normalize_arxiv_id(_metadata_value(item.metadata, key))
        if arxiv_id:
            return arxiv_id

    if item.source_name.lower() == "arxiv":
        arxiv_id = normalize_arxiv_id(item.external_id)
        if arxiv_id:
            return arxiv_id

    parsed = urlsplit(item.url)
    if (parsed.hostname or "").lower() == "arxiv.org":
        return normalize_arxiv_id(item.url)
    return ""


def _item_github_repo(item: ResearchItem) -> str:
    for key in ("full_name", "repo_full_name", "repository", "repo_url", "html_url", "url"):
        repo = normalize_github_repo(_metadata_value(item.metadata, key))
        if repo:
            return repo

    if item.source_name.lower() == "github" or item.item_type.lower() in {"repo", "repository"}:
        for value in (item.title, item.url, item.external_id):
            repo = normalize_github_repo(value)
            if repo:
                return repo

    repo = normalize_github_repo(item.url)
    if repo:
        return repo
    return ""


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    for candidate, value in metadata.items():
        if candidate.lower() == key:
            return value
    return None


def _normalize_http_scheme_and_host(scheme: str, netloc: str) -> tuple[str, str]:
    host_port = netloc.rsplit("@", 1)[-1]
    has_port = ":" in host_port
    if netloc.endswith(":80") or netloc.endswith(":443"):
        netloc = netloc.rsplit(":", 1)[0]
        return "https", netloc
    if not has_port:
        return "https", netloc
    return scheme, netloc


def _is_tracking_param(key: str) -> bool:
    normalized = key.strip().lower()
    return normalized.startswith("utm_") or normalized in TRACKING_QUERY_PARAMS


def _clean_github_full_name(value: str) -> str:
    cleaned = value.strip().strip("/")
    cleaned = cleaned.removesuffix(".git")
    return cleaned.lower()


def _is_punctuation(char: str) -> bool:
    return char in string.punctuation or unicodedata.category(char).startswith("P")


__all__ = [
    "item_fingerprint",
    "normalize_arxiv_id",
    "normalize_canonical_url",
    "normalize_doi",
    "normalize_github_repo",
    "normalize_pubmed_id",
    "normalize_title",
]
