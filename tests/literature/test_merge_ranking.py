from __future__ import annotations

from datetime import UTC, datetime

from paperagent.literature.coverage import audit_coverage
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.ranking import rank_papers
from paperagent.schemas.literature import (
    LiteratureFilters,
    LiteratureQueryPlan,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def result(provider: str, papers: list[ProviderPaper]) -> ProviderResult:
    return ProviderResult(
        provider=provider,
        request_id=f"req-{provider}",
        status="success" if papers else "empty",
        papers=papers,
        started_at=NOW,
        finished_at=NOW,
    )


def _plan() -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question="Which retrieval method covers failures and benchmarks?",
        scope="information retrieval",
        required_gap_ids=["method", "failure"],
        query_lanes=[
            QueryLane(
                lane_id="l1",
                purpose="method",
                query="retrieval method benchmark",
                gap_ids=["method"],
            ),
            QueryLane(
                lane_id="l2",
                purpose="limitation_failure",
                query="retrieval failure limitation",
                gap_ids=["failure"],
            ),
        ],
        filters=LiteratureFilters(year_min=2020, year_max=2026),
    )


def test_same_doi_merges_provenance_and_richer_metadata() -> None:
    openalex = ProviderPaper(
        provider_record_id="oa1",
        title="Reliable Retrieval Systems",
        authors=["A. Smith"],
        year=2024,
        doi="https://doi.org/10.1000/ABC",
        abstract="short",
        openalex_id="W1",
        matched_gap_ids=["method"],
    )
    s2 = ProviderPaper(
        provider_record_id="s21",
        title="Reliable Retrieval Systems",
        authors=["A. Smith", "B. Doe"],
        year=2024,
        doi="10.1000/abc",
        abstract="a substantially more complete abstract",
        semantic_scholar_id="S1",
        matched_gap_ids=["failure"],
    )
    merged = merge_provider_results(
        [result("openalex", [openalex]), result("semantic_scholar", [s2])]
    )
    assert len(merged) == 1
    paper = merged[0]
    assert paper.doi == "10.1000/abc"
    assert paper.abstract == "a substantially more complete abstract"
    assert {record.provider for record in paper.source_records} == {
        "openalex",
        "semantic_scholar",
    }
    assert paper.matched_gap_ids == ["failure", "method"]


def test_same_title_year_author_merges_without_identifier() -> None:
    first = ProviderPaper(
        provider_record_id="a",
        title="A Study of Retrieval",
        authors=["Jane Doe"],
        year=2023,
    )
    second = ProviderPaper(
        provider_record_id="b",
        title="A study of retrieval!",
        authors=["Jane Doe"],
        year=2023,
    )
    merged = merge_provider_results([result("openalex", [first]), result("arxiv", [second])])
    assert len(merged) == 1


def test_title_collision_with_different_author_does_not_merge() -> None:
    first = ProviderPaper(
        provider_record_id="a",
        title="A Study of Retrieval",
        authors=["Jane Doe"],
        year=2023,
    )
    second = ProviderPaper(
        provider_record_id="b",
        title="A Study of Retrieval",
        authors=["John Roe"],
        year=2023,
    )
    merged = merge_provider_results([result("openalex", [first]), result("arxiv", [second])])
    assert len(merged) == 2


def test_conflicting_year_adds_warning() -> None:
    first = ProviderPaper(
        provider_record_id="a",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2022,
        doi="10.1/x",
    )
    second = ProviderPaper(
        provider_record_id="b",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2024,
        doi="10.1/x",
    )
    merged = merge_provider_results([result("openalex", [first]), result("arxiv", [second])])
    assert {warning.code for warning in merged[0].merge_warnings} == {"YEAR_CONFLICT"}


def test_irrelevant_high_citation_paper_cannot_outrank_relevant_uncited_paper() -> None:
    irrelevant = ProviderPaper(
        provider_record_id="old",
        title="Protein Folding Survey",
        authors=["A"],
        year=2020,
        citation_count=100000,
        matched_gap_ids=[],
    )
    relevant = ProviderPaper(
        provider_record_id="new",
        title="Retrieval Method Failure Benchmark",
        authors=["B"],
        year=2026,
        citation_count=0,
        matched_gap_ids=["method", "failure"],
    )
    papers = merge_provider_results([result("openalex", [irrelevant, relevant])])
    ranked = rank_papers(papers, _plan(), now_year=2026)
    assert ranked[0].canonical_title == relevant.title
    assert ranked[0].rank_features is not None
    assert ranked[0].rank_features.score > ranked[1].rank_features.score


def test_coverage_audit_requests_retry_for_uncovered_required_gap() -> None:
    relevant = ProviderPaper(
        provider_record_id="new",
        title="Retrieval Method Benchmark",
        authors=["B"],
        year=2026,
        matched_gap_ids=["method"],
    )
    paper = merge_provider_results([result("openalex", [relevant])])[0].model_copy(
        update={"verification_status": "verified"}
    )
    coverage = audit_coverage([paper], _plan(), round_number=1)
    assert coverage.uncovered_gap_ids == ["failure"]
    assert coverage.retry_recommendation == "focused_retry"


def test_coverage_audit_marks_budget_exhausted_on_second_round() -> None:
    coverage = audit_coverage([], _plan(), round_number=2)
    assert coverage.retry_recommendation == "budget_exhausted"
