"""Session 26: Evidence Promotion tests (SOP §6).

覆盖 8 个后端测试：
1. 未 selected -> blocked
2. URL 未验证 -> blocked
3. URL failed -> blocked
4. verified + selected + user_confirmed -> promoted
5. partial -> eligible 但带 warning
6. promoted EvidenceRef 反向引用 candidate_id
7. EvidenceRef 不含 report final claim
8. candidate_is_not_evidence 仍通过
"""

from __future__ import annotations

import pytest

from app.schemas_candidates import CandidateResource, candidate_is_not_evidence
from app.schemas_evidence_promotion import (
    EvidencePromotionRequest,
    EvidencePromotionResult,
    PromotionGateInput,
    URLVerificationRecord,
    check_promotion_gate,
    promote_to_evidence,
)


# ---------- S26-B-1: 未 selected -> blocked ---------- #


class TestNotSelectedBlocked:
    def test_unselected_candidate_blocked(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=False,
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert any("not selected" in b.lower() for b in result.blockers)

    def test_unselected_blocks_even_if_verified(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=False,
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp)
        assert result.status == "blocked"
        assert result.evidence_ref is None


# ---------- S26-B-2: URL 未验证 -> blocked ---------- #


class TestURLUncheckedBlocked:
    def test_unchecked_url_blocked(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="unchecked",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert any("not verified" in b.lower() for b in result.blockers)


# ---------- S26-B-3: URL failed -> blocked ---------- #


class TestURLFailedBlocked:
    def test_failed_url_blocked(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="failed",
            url_failure_reason="404 Not Found",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert any("failed" in b.lower() for b in result.blockers)
        assert any("404" in b for b in result.blockers)

    def test_expired_url_blocked(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="expired",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert any("expired" in b.lower() for b in result.blockers)


# ---------- S26-B-4: verified + selected + user_confirmed -> promoted ---------- #


class TestFullPromotion:
    def test_promoted_when_all_conditions_met(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            candidate_title="YOLO Steel Detection",
            candidate_kind="paper",
            candidate_url="https://example.com/yolo",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=True,
            promotion_reason="Key paper for baseline comparison",
        )
        result = promote_to_evidence(inp)
        assert result.status == "promoted"
        assert result.evidence_ref is not None
        assert result.evidence_ref.title == "YOLO Steel Detection"
        assert result.evidence_ref.url == "https://example.com/yolo"
        assert result.evidence_ref.url_verified is True

    def test_eligible_gate_returns_eligible(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "eligible"
        assert len(result.blockers) == 0


# ---------- S26-B-5: partial -> eligible 但带 warning ---------- #


class TestPartialURLWarning:
    def test_partial_url_eligible_with_warning(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            candidate_title="Partially Verified Paper",
            candidate_kind="paper",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="partial",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp)
        assert result.status == "promoted"
        assert len(result.warnings) > 0
        assert any("partially" in w.lower() or "partial" in w.lower() for w in result.warnings)

    def test_partial_gate_returns_eligible_with_warning(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="partial",
            user_confirmed=True,
        )
        result = check_promotion_gate(inp)
        assert result.status == "eligible"
        assert len(result.warnings) > 0


# ---------- S26-B-6: promoted EvidenceRef 反向引用 candidate_id ---------- #


class TestEvidenceRefBackReference:
    def test_evidence_ref_has_candidate_id_in_reason(self):
        inp = PromotionGateInput(
            candidate_id="cand_042",
            candidate_title="Back-ref Paper",
            candidate_kind="paper",
            candidate_url="https://example.com/42",
            is_selected=True,
            selected_id="sel_042",
            url_verification_status="verified",
            user_confirmed=True,
            promotion_reason="Promoted from candidate cand_042",
        )
        result = promote_to_evidence(inp, evidence_id="ev_cand_042")
        assert result.status == "promoted"
        assert result.evidence_ref.evidence_id == "ev_cand_042"
        assert "cand_042" in result.evidence_ref.reason

    def test_custom_evidence_id(self):
        inp = PromotionGateInput(
            candidate_id="cand_100",
            candidate_title="Custom ID Paper",
            is_selected=True,
            selected_id="sel_100",
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp, evidence_id="ev_custom_abc")
        assert result.evidence_ref.evidence_id == "ev_custom_abc"


# ---------- S26-B-7: EvidenceRef 不含 report final claim ---------- #


class TestEvidenceRefNoFinalClaim:
    def test_no_supports_field(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            candidate_title="Test Paper",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp)
        assert result.evidence_ref is not None
        # EvidenceRef should have role="supports" by default but NOT contain
        # final report paragraph or conclusion
        assert not hasattr(result.evidence_ref, "report_paragraph")
        assert not hasattr(result.evidence_ref, "conclusion")
        # review_status should be pending, not final
        assert result.evidence_ref.review_status == "pending"


# ---------- S26-B-8: candidate_is_not_evidence 仍通过 ---------- #


class TestCandidateStillNotEvidence:
    def test_candidate_schema_unchanged(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert candidate_is_not_evidence(cand) is True

    def test_promoted_candidate_is_still_not_evidence(self):
        """晋升操作不影响原始 CandidateResource — 它仍然是候选."""
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        # Promote separately
        inp = PromotionGateInput(
            candidate_id="cand_001",
            candidate_title="Test Paper",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=True,
        )
        result = promote_to_evidence(inp)
        # Original candidate is still not evidence
        assert candidate_is_not_evidence(cand) is True
        # But the promoted EvidenceRef exists
        assert result.evidence_ref is not None


# ---------- Extra: user_confirmed=False blocked ---------- #


class TestUserNotConfirmed:
    def test_user_not_confirmed_blocked(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=True,
            selected_id="sel_001",
            url_verification_status="verified",
            user_confirmed=False,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert any("not confirmed" in b.lower() or "user" in b.lower() for b in result.blockers)


# ---------- Extra: multi-blocker aggregation ---------- #


class TestMultipleBlockers:
    def test_all_blockers_collected(self):
        inp = PromotionGateInput(
            candidate_id="cand_001",
            is_selected=False,
            url_verification_status="unchecked",
            user_confirmed=False,
        )
        result = check_promotion_gate(inp)
        assert result.status == "blocked"
        assert len(result.blockers) == 3  # not selected, not verified, not confirmed
