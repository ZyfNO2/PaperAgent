from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from paperagent.nodes.evidence_synthesis import _compact_evidence_payload
from paperagent.schemas import EvidenceItem


def test_compact_payload_bounds_untrusted_text_and_metadata() -> None:
    item = EvidenceItem(
        evidence_id="ev-long",
        source_type="paper",
        title="Long evidence",
        locator="https://example.test/long",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="s" * 5000,
        content_hash="sha256:long",
        metadata={
            "query_text": "q" * 900,
            "relation": "direct_query",
            "irrelevant_large_field": "z" * 5000,
        },
    )
    payload = _compact_evidence_payload(item)
    assert len(cast(str, payload["summary"])) == 800
    metadata = cast(dict[str, str], payload["metadata"])
    assert len(metadata["query_text"]) == 500
    assert metadata["relation"] == "direct_query"
    assert "irrelevant_large_field" not in metadata


def test_compact_payload_preserves_identity_and_gap_bindings() -> None:
    item = EvidenceItem(
        evidence_id="ev-identity",
        source_type="repository",
        title="authors/project",
        locator="https://example.test/repo",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g-baseline", "g-module"],
        summary="verified implementation",
        content_hash="sha256:identity",
        metadata={"relation": "author_linked_from_verified_paper"},
    )
    payload = _compact_evidence_payload(item)
    assert payload["evidence_id"] == "ev-identity"
    assert payload["supports_gap_ids"] == ["g-baseline", "g-module"]
