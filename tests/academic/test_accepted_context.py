from __future__ import annotations

import pytest

from paperagent.academic.context import (
    AcademicEvidenceInsufficientError,
    build_accepted_context_manifest,
)
from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicEvidenceEntry,
    AcademicEvidenceLedger,
    AcademicLocator,
)


def _locator(object_id: str) -> AcademicLocator:
    return AcademicLocator(
        schema_version="academic.v1",
        paper_id="paper-1",
        version_id="v1",
        object_id=object_id,
        page_number=1,
        object_type="paragraph",
        source_hash="a" * 64,
    )


class _Source:
    def __init__(self, candidates: dict[str, AcademicCandidate]) -> None:
        self.candidates = candidates

    def retrieve(self, request):  # pragma: no cover - context builder never retrieves
        raise AssertionError("unexpected retrieval")

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        return self.candidates[locator.object_id]


def _candidate(evidence_id: str, object_id: str, text: str = "grounded") -> AcademicCandidate:
    return AcademicCandidate(
        evidence_id=evidence_id,
        locator=_locator(object_id),
        text=text,
        score=1,
        provenance="extracted",
    )


def _ledger(*entries: AcademicEvidenceEntry) -> AcademicEvidenceLedger:
    return AcademicEvidenceLedger(
        entries=entries,
        accepted_ids=tuple(x.evidence_id for x in entries if x.status == "accepted"),
        rejected_ids=tuple(x.evidence_id for x in entries if x.status == "rejected"),
        conflicted_ids=tuple(x.evidence_id for x in entries if x.status == "conflicted"),
    )


def test_manifest_contains_only_accepted_resolved_evidence_and_is_bounded() -> None:
    accepted = AcademicEvidenceEntry(evidence_id="ok", locator=_locator("o1"), status="accepted")
    rejected = AcademicEvidenceEntry(evidence_id="no", locator=_locator("o2"), status="rejected")
    conflicted = AcademicEvidenceEntry(
        evidence_id="bad", locator=_locator("o3"), status="conflicted"
    )
    source = _Source({"o1": _candidate("ok", "o1", "123456789")})
    manifest = build_accepted_context_manifest(
        _ledger(accepted, rejected, conflicted),
        source,
        character_budget=5,
        token_budget=10,
        retrieval_trace_ids=("trace-1",),
    )
    assert manifest.evidence_ids == ("ok",)
    assert manifest.entries[0].text == "12345"
    assert manifest.characters_used == 5
    assert manifest.tokens_used == 5
    assert manifest.retrieval_trace_ids == ("trace-1",)


def test_empty_or_unresolvable_accepted_ledger_abstains() -> None:
    with pytest.raises(AcademicEvidenceInsufficientError, match="no accepted"):
        build_accepted_context_manifest(
            _ledger(),
            _Source({}),
            character_budget=10,
            token_budget=10,
            retrieval_trace_ids=(),
        )
    entry = AcademicEvidenceEntry(evidence_id="ok", locator=_locator("missing"), status="accepted")
    with pytest.raises(AcademicEvidenceInsufficientError, match="not resolvable"):
        build_accepted_context_manifest(
            _ledger(entry),
            _Source({}),
            character_budget=10,
            token_budget=10,
            retrieval_trace_ids=(),
        )


def test_token_budget_is_enforced_for_non_ascii_text() -> None:
    entry = AcademicEvidenceEntry(evidence_id="ok", locator=_locator("o1"), status="accepted")
    source = _Source({"o1": _candidate("ok", "o1", "混凝土crack")})

    manifest = build_accepted_context_manifest(
        _ledger(entry),
        source,
        character_budget=100,
        token_budget=6,
        retrieval_trace_ids=(),
    )

    assert manifest.entries[0].text == "混凝"
    assert manifest.tokens_used == 6
    assert manifest.tokens_used <= manifest.token_budget


def test_source_identity_drift_fails_closed() -> None:
    entry = AcademicEvidenceEntry(evidence_id="expected", locator=_locator("o1"), status="accepted")
    source = _Source({"o1": _candidate("different", "o1")})
    with pytest.raises(AcademicEvidenceInsufficientError, match="source identity"):
        build_accepted_context_manifest(
            _ledger(entry),
            source,
            character_budget=10,
            token_budget=10,
            retrieval_trace_ids=(),
        )
