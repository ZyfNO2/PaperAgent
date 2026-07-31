from __future__ import annotations

from paperagent.academic.claims import (
    GeneratedClaim,
    check_citation_claim_mismatch,
    generate_claims_from_ledger,
)
from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicEvidenceEntry,
    AcademicEvidenceLedger,
    AcademicLocator,
)


def _locator(*, object_id: str = "object-1", source_hash: str = "a" * 64) -> AcademicLocator:
    return AcademicLocator(
        schema_version="academic.v1",
        paper_id="paper-1",
        version_id="v1",
        object_id=object_id,
        page_number=1,
        object_type="paragraph",
        source_hash=source_hash,
    )


def _ledger() -> AcademicEvidenceLedger:
    entry = AcademicEvidenceEntry(evidence_id="e1", locator=_locator(), status="accepted")
    return AcademicEvidenceLedger(
        entries=(entry,), accepted_ids=("e1",), rejected_ids=(), conflicted_ids=()
    )


class _Source:
    def __init__(self, resolved: AcademicCandidate | Exception) -> None:
        self.resolved = resolved

    def retrieve(self, request):
        raise AssertionError("unexpected retrieve")

    def resolve(self, locator):
        if isinstance(self.resolved, Exception):
            raise self.resolved
        return self.resolved


def test_claim_generation_is_deterministic_and_accepted_only() -> None:
    resolved = AcademicCandidate(
        evidence_id="e1",
        locator=_locator(),
        text="The method achieves 91.2 percent F1 on Crack500 test.",
        score=1,
        provenance="extracted",
    )
    source = _Source(resolved)
    first = generate_claims_from_ledger(_ledger(), source, question="What is supported?")
    second = generate_claims_from_ledger(_ledger(), source, question="What is supported?")
    assert first == second
    assert first[0].text == resolved.text.rstrip(".")
    assert first[0].evidence_ids == ("e1",)
    assert first[0].locator_bindings == (_locator(),)


def test_unresolvable_and_wrong_object_citations_fail_closed() -> None:
    claim = GeneratedClaim("c1", "claim", ("e1",), (_locator(),))
    unresolved = check_citation_claim_mismatch((claim,), _Source(KeyError("gone")))
    assert [item.kind for item in unresolved] == ["locator_unresolvable"]
    wrong = AcademicCandidate(
        evidence_id="e1",
        locator=_locator(object_id="other"),
        text="text",
        score=1,
        provenance="extracted",
    )
    mismatch = check_citation_claim_mismatch((claim,), _Source(wrong))
    assert {item.kind for item in mismatch} == {
        "locator_identity_mismatch",
        "semantic_support_mismatch",
    }


def test_source_hash_mismatch_is_hard_failure() -> None:
    claim = GeneratedClaim("c1", "claim", ("e1",), (_locator(),))
    changed = AcademicCandidate(
        evidence_id="e1",
        locator=_locator(source_hash="b" * 64),
        text="text",
        score=1,
        provenance="extracted",
    )
    mismatch = check_citation_claim_mismatch((claim,), _Source(changed))
    assert {item.kind for item in mismatch} == {
        "source_hash_mismatch",
        "semantic_support_mismatch",
    }


def test_semantic_and_numeric_mismatches_fail_closed() -> None:
    claim = GeneratedClaim(
        "c1",
        "The method achieves 95 percent F1.",
        ("e1",),
        (_locator(),),
    )
    resolved = AcademicCandidate(
        evidence_id="e1",
        locator=_locator(),
        text="The method achieves 91.2 percent F1.",
        score=1,
        provenance="extracted",
    )

    mismatch = check_citation_claim_mismatch((claim,), _Source(resolved))

    assert {item.kind for item in mismatch} == {
        "semantic_support_mismatch",
        "numeric_value_mismatch",
    }
