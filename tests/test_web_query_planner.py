from __future__ import annotations

from backend.search.web_query_planner import WebQueryPlanner


def test_query_planner_expands_keyword_string_into_multiple_categories() -> None:
    planner = WebQueryPlanner(
        categories=["general", "news", "blog", "dataset", "benchmark", "code"],
        max_queries=10,
    )

    queries = planner.plan("single-cell foundation model perturbation prediction drug response")

    assert "single-cell foundation model perturbation prediction drug response" in queries
    assert "single-cell foundation model perturbation prediction drug response benchmark" in queries
    assert "single-cell foundation model perturbation prediction drug response dataset" in queries
    assert "single-cell foundation model perturbation prediction drug response blog" in queries
    assert "single-cell foundation model perturbation prediction drug response news" in queries
    assert "single-cell foundation model drug response GitHub" in queries


def test_query_planner_includes_profile_terms_without_duplicate_queries() -> None:
    planner = WebQueryPlanner(categories=["general"], max_queries=5)

    planned = planner.plan_with_categories(
        ["single-cell", "drug response"],
        user_profile="Interested in BioPatchFM and BioPatchFM updates.",
    )

    assert planned[0].query == "single-cell drug response"
    assert any(query.query.startswith("BioPatchFM single-cell drug response") for query in planned)
    assert len({query.query.lower() for query in planned}) == len(planned)
