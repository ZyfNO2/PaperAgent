from __future__ import annotations

from pathlib import Path

TEST = Path("tests/methodology/test_scientific_decision_policy.py")


def replace_once(old: str, new: str, label: str) -> None:
    source = TEST.read_text(encoding="utf-8")
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError(f"{TEST}: missing {label}")
    TEST.write_text(source, encoding="utf-8")


def main() -> int:
    replace_once(
        '''from __future__ import annotations

from test_method_design_draft import _draft, _state

from paperagent.academic_methodology import AuditSeverity, AuditVerdict, audit_method_plan
''',
        '''from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from test_method_design_draft import _draft, _state

from paperagent.academic_methodology import AuditSeverity, AuditVerdict, audit_method_plan
''',
        "policy fixture imports",
    )
    replace_once(
        '''from paperagent.method_design_draft import build_method_proposal
from paperagent.method_evidence import bind_method_evidence


def _proposal(**updates: object):
    state = _state()
    proposal = build_method_proposal(state, _draft(**updates))
''',
        '''from paperagent.method_design_draft import build_method_proposal
from paperagent.method_evidence import bind_method_evidence
from paperagent.schemas import Claim, EvidenceItem
from paperagent.state import PaperAgentState


def _with_independent_comparator(state: PaperAgentState) -> PaperAgentState:
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    assert evidence is not None
    assert synthesis is not None
    comparator_id = "ev-policy-rt-detr-r18"
    comparator = EvidenceItem(
        evidence_id=comparator_id,
        source_type="paper",
        title="RT-DETR-R18",
        locator="doi:10.1000/policy-rt-detr-r18",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary=(
            "RT-DETR-R18 is an independently retrieved strong-comparison paper with a "
            "verified identity."
        ),
        content_hash="sha256:policy-rt-detr-r18",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/policy-rt-detr-r18",
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.95",
        },
    )
    comparator_claim = Claim(
        claim_id="claim-policy-rt-detr-r18",
        text=(
            "RT-DETR-R18 provides an independently identified strong-comparison paper "
            "for the matched detector evaluation."
        ),
        evidence_ids=[comparator_id],
    )
    return cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, comparator],
                    "accepted_ids": [*evidence.accepted_ids, comparator_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        comparator_id,
                    ],
                    "coverage_by_gap": {
                        **evidence.coverage_by_gap,
                        "baseline_comparison": (
                            evidence.coverage_by_gap.get("baseline_comparison", 0) + 1
                        ),
                    },
                }
            ),
            "synthesis": synthesis.model_copy(
                update={
                    "verified_findings": [
                        *synthesis.verified_findings,
                        comparator_claim,
                    ]
                }
            ),
        },
    )


def _proposal(**updates: object):
    state = _state()
    if updates.get("comparison_readiness_confirmed") is True:
        state = _with_independent_comparator(state)
    proposal = build_method_proposal(state, _draft(**updates))
''',
        "comparison-ready fixture",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
