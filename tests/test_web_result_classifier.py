from __future__ import annotations

from backend.search.search_result import SearchResult
from backend.search.web_result_classifier import WebResultClassifier


def result(url: str, title: str = "Result", snippet: str = "") -> SearchResult:
    return SearchResult(title=title, url=url, snippet=snippet, source="searxng")


def test_result_classifier_labels_github_as_code() -> None:
    classifier = WebResultClassifier()

    assert classifier.classify(result("https://github.com/owner/repo")) == "code"


def test_result_classifier_labels_nature_biorxiv_pubmed_as_paper() -> None:
    classifier = WebResultClassifier()

    assert classifier.classify(result("https://www.nature.com/articles/s41586-026-00001")) == "paper"
    assert classifier.classify(result("https://www.biorxiv.org/content/10.1101/2026.05.19.000001v1")) == "paper"
    assert classifier.classify(result("https://pubmed.ncbi.nlm.nih.gov/123456/")) == "paper"


def test_result_classifier_labels_dataset_domains_as_dataset() -> None:
    classifier = WebResultClassifier()

    assert classifier.classify(result("https://www.kaggle.com/datasets/example/single-cell")) == "dataset"
    assert classifier.classify(result("https://huggingface.co/datasets/org/single-cell")) == "dataset"
    assert classifier.classify(result("https://zenodo.org/records/123456")) == "dataset"


def test_result_classifier_labels_benchmark_and_lab_pages() -> None:
    classifier = WebResultClassifier()

    assert classifier.classify(result("https://example.com/leaderboard", title="Perturbation benchmark")) == "benchmark"
    assert classifier.classify(result("https://lab.stanford.edu/group/update", title="Research group update")) == "lab_page"
