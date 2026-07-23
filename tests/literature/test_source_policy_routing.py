from paperagent.literature.source_policy import review_search_query
from paperagent.schemas import SearchQuery


def query(text: str) -> SearchQuery:
    return SearchQuery(query_id="q1", gap_id="g1", query=text, source_types=["paper"])


def test_general_academic_search_does_not_call_arxiv_by_default() -> None:
    policy = review_search_query(query("industrial anomaly detection transformer comparison"))

    assert policy.approved is True
    assert policy.primary_provider == "openalex"
    assert policy.escalation_providers == ("semantic_scholar",)


def test_recent_search_uses_arxiv_only_after_primary_sources() -> None:
    policy = review_search_query(
        query("industrial anomaly detection transformer methods published in 2026")
    )

    assert policy.primary_provider == "openalex"
    assert policy.escalation_providers == ("semantic_scholar", "arxiv")


def test_explicit_preprint_request_routes_to_arxiv_first() -> None:
    policy = review_search_query(query("latest arxiv preprint industrial anomaly detection"))

    assert policy.primary_provider == "arxiv"
    assert policy.escalation_providers == ("openalex", "semantic_scholar")
