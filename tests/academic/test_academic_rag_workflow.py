from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from paperagent.academic import (
    AcademicCandidate,
    AcademicEvidenceSource,
    AcademicLocator,
    AcademicRAGWorkflow,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
)


def _candidate(
    *, object_type: str = "paragraph", text: str = "Supported evidence."
) -> AcademicCandidate:
    return AcademicCandidate(
        evidence_id=f"paper-1:{object_type}:1",
        locator=AcademicLocator(
            schema_version="academic.v1",
            paper_id="paper-1",
            version_id="version-1",
            object_id=f"{object_type}-1",
            page_number=2,
            object_type=object_type,
            source_hash="a" * 64,
            bounding_box=(10.0, 20.0, 30.0, 40.0),
        ),
        text=text,
        score=0.9,
        provenance="extracted",
    )


@dataclass
class FakeEvidenceSource(AcademicEvidenceSource):
    results: list[AcademicRetrievalResult]
    requests: list[AcademicRetrievalRequest] = field(default_factory=list)

    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult:
        self.requests.append(request)
        return self.results.pop(0)

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        return _candidate(object_type=locator.object_type)


def test_exact_identity_is_preserved_and_primary_retrieval_is_bounded() -> None:
    source = FakeEvidenceSource(
        [
            AcademicRetrievalResult(
                candidates=(_candidate(),),
                sufficiency="sufficient",
                reasons=("direct evidence",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id="trace-primary",
            )
        ]
    )

    result = AcademicRAGWorkflow(source).run(
        project_id="project-1",
        question="Explain DOI 10.1234/ABC.Def architecture.",
    )

    assert len(source.requests) == 1
    assert source.requests[0].round_kind == "primary"
    assert "10.1234/ABC.Def" in source.requests[0].query
    assert result.query_plan.kind == "identity"
    assert result.query_plan.exact_identifiers == ("10.1234/ABC.Def",)
    assert result.ledger.accepted_ids == ("paper-1:paragraph:1",)
    assert result.stop_reason == "sufficient"


def test_visual_degradation_is_partial_even_when_text_candidate_exists() -> None:
    source = FakeEvidenceSource(
        [
            AcademicRetrievalResult(
                candidates=(_candidate(object_type="caption"),),
                sufficiency="sufficient",
                reasons=("caption matched",),
                degraded_channels=("visual",),
                conflict_detected=False,
                trace_id="trace-visual",
            )
        ]
    )

    result = AcademicRAGWorkflow(source).run(
        project_id="project-1",
        question="Where is the attention module connected in Figure 3?",
    )

    assert result.query_plan.kind == "figure"
    assert "visual" in result.query_plan.channels
    assert result.sufficiency == "partial"
    assert result.stop_reason == "visual_channel_degraded"


def test_corrective_and_conflict_rounds_run_at_most_once_each() -> None:
    source = FakeEvidenceSource(
        [
            AcademicRetrievalResult(
                candidates=(),
                sufficiency="insufficient",
                reasons=("missing result",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id="trace-primary",
            ),
            AcademicRetrievalResult(
                candidates=(_candidate(text="F1 is 91.2."),),
                sufficiency="partial",
                reasons=("one result",),
                degraded_channels=(),
                conflict_detected=True,
                trace_id="trace-corrective",
            ),
            AcademicRetrievalResult(
                candidates=(_candidate(text="F1 is reported as 91.2."),),
                sufficiency="sufficient",
                reasons=("conflict resolved",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id="trace-conflict",
            ),
        ]
    )

    result = AcademicRAGWorkflow(source).run(
        project_id="project-1",
        question="What F1 is reported in Table 3?",
    )

    assert [request.round_kind for request in source.requests] == [
        "primary",
        "corrective",
        "conflict",
    ]
    assert result.rounds_used == {"primary": 1, "corrective": 1, "conflict": 1}
    assert result.sufficiency == "sufficient"


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("Read Table 2.", "table"),
        ("Explain Equation 4.", "equation"),
        ("Compare the two methods.", "comparison"),
        ("Which baseline module should be ablated?", "tailoring"),
        ("Describe the training method.", "method"),
    ],
)
def test_query_router_covers_academic_query_kinds(
    question: str,
    kind: str,
) -> None:
    source = FakeEvidenceSource(
        [
            AcademicRetrievalResult(
                candidates=(_candidate(),),
                sufficiency="sufficient",
                reasons=("matched",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id=f"trace-{kind}",
            )
        ]
    )

    result = AcademicRAGWorkflow(source).run(
        project_id="project-1",
        question=question,
    )

    assert result.query_plan.kind == kind


def test_empty_question_is_rejected() -> None:
    source = FakeEvidenceSource([])

    with pytest.raises(ValueError, match="question"):
        AcademicRAGWorkflow(source).run(project_id="project-1", question=" ")


def test_unresolvable_and_changed_candidates_are_not_accepted() -> None:
    first = _candidate(text="Metric is 0.8.")
    second = _candidate(text="Metric is 0.9.")

    @dataclass
    class UnresolvableSource(FakeEvidenceSource):
        def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
            raise KeyError(locator.object_id)

    source = UnresolvableSource(
        [
            AcademicRetrievalResult(
                candidates=(first,),
                sufficiency="insufficient",
                reasons=("needs correction",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id="trace-primary",
            ),
            AcademicRetrievalResult(
                candidates=(second,),
                sufficiency="partial",
                reasons=("conflicting candidate",),
                degraded_channels=(),
                conflict_detected=False,
                trace_id="trace-corrective",
            ),
        ]
    )

    result = AcademicRAGWorkflow(source).run(
        project_id="project-1",
        question="Describe the method.",
    )

    assert result.ledger.accepted_ids == ()
    assert result.ledger.conflicted_ids == (first.evidence_id,)
