"""Re7.6 D-09 Novelty Pipeline Acceptance Tests.

SOP §7.1: Two mandatory acceptance verifications for the novelty pipeline:

验收1 — Real topic:
  - novelty_draft only produces ``draft`` / ``needs_evidence`` status
  - Each Problem / Method / Insight binds real evidence_ids from EvidenceContext

验收2 — No-evidence fixture:
  - Drafts are never auto-``accepted``
  - Claim Judge blocks first claim without evidence
  - Missing support / refute / test conditions are blocked
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from apps.api.app.services.agents.graph.nodes.novelty_draft import (
    _heuristic_draft,
    parse_draft_output,
    novelty_draft_node,
)


# ── Shared fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def real_topic_state():
    """Simulate XD-01: steel surface defect detection with evidence_contexts."""
    return {
        "topic": "基于视觉 Transformer 的钢材表面缺陷检测",
        "evidence_contexts": [
            {"candidate_id": "ev-vit-0", "role": "method", "snippet": "ViT breaks image into patches",
             "location": "doi:10.xxxx/vit", "source_quality": "verified"},
            {"candidate_id": "ev-cbam-1", "role": "method", "snippet": "CBAM attention module",
             "location": "doi:10.xxxx/cbam", "source_quality": "verified"},
            {"candidate_id": "ev-neu-2", "role": "problem", "snippet": "NEU-DET benchmark for steel defects",
             "location": "doi:10.xxxx/neu", "source_quality": "verified"},
            {"candidate_id": "ev-gc10-3", "role": "problem", "snippet": "GC10-DET has 10 defect types",
             "location": "doi:10.xxxx/gc10", "source_quality": "verified"},
            {"candidate_id": "ev-deep-4", "role": "insight", "snippet": "Deep learning for defect detection survey",
             "location": "doi:10.xxxx/deep", "source_quality": "verified"},
            {"candidate_id": "ev-yolo-5", "role": "adjacent", "snippet": "YOLO-based defect detection",
             "location": "doi:10.xxxx/yolo", "source_quality": "verified"},
        ],
        "innovation_points": [
            {
                "description": "在ViT基础上引入CBAM注意力机制和特征金字塔",
                "baseline_used": "ViT",
                "stitched_modules": ["CBAM", "FPN"],
                "stitching_plan": "通过CBAM关注缺陷区域、FPN融合多尺度特征，提高小缺陷检测精度",
                "estimated_difficulty": "中",
                "evidence_ref": "ev-vit-0",
                "candidate_ids": ["ev-vit-0", "ev-cbam-1", "ev-neu-2", "ev-gc10-3", "ev-deep-4"],
                "novelty_score": 6.0,
                "feasibility_score": 7.0,
                "evidence_score": 6.5,
                "status": "pending",
            }
        ],
        "baseline_candidates": [
            {"title": "Vision Transformer (ViT)", "id": "vit-paper"},
            {"title": "CBAM: Convolutional Block Attention Module", "id": "cbam-paper"},
        ],
    }


@pytest.fixture
def no_evidence_state():
    """Innovation points exist but NO evidence_contexts at all."""
    return {
        "topic": "基于新机制的量子计算加速器设计",
        "evidence_contexts": [],
        "innovation_points": [
            {
                "description": "首次提出基于拓扑量子纠错的新型加速器架构",
                "baseline_used": "Surface Code",
                "stitched_modules": ["拓扑编码", "容错门"],
                "stitching_plan": "通过拓扑编码降低逻辑错误率到10^-6以下",
                "estimated_difficulty": "高",
                "evidence_ref": "",
                "candidate_ids": [],
                "novelty_score": 8.0,
                "feasibility_score": 3.0,
                "evidence_score": 0.0,
                "status": "pending",
            }
        ],
        "baseline_candidates": [
            {"title": "Surface Code"},
        ],
    }


@pytest.fixture
def empty_innovation_state():
    """No innovation points at all."""
    return {
        "topic": "test",
        "evidence_contexts": [],
        "innovation_points": [],
        "baseline_candidates": [],
    }


# ══════════════════════════════════════════════════════════════════════
# 验收1: Real topic — draft → draft/needs_evidence, each P/M/I binds evidence
# ══════════════════════════════════════════════════════════════════════

class TestAcceptanceRealTopic:
    """验收1: 真实题目场景验证."""

    def test_heuristic_draft_never_accepted(self, real_topic_state):
        """_heuristic_draft should never produce 'accepted' status."""
        drafts = _heuristic_draft(real_topic_state)
        assert len(drafts) >= 1
        for d in drafts:
            assert d["status"] in ("draft", "needs_evidence"), \
                f"found status={d['status']} — never auto-accepted"

    def test_heuristic_draft_has_pmi_structure(self, real_topic_state):
        """Each draft must have problem/method/insight."""
        drafts = _heuristic_draft(real_topic_state)
        for d in drafts:
            assert "problem" in d and d["problem"], "missing problem"
            assert "method" in d and d["method"], "missing method"
            assert "insight" in d and d["insight"], "missing insight"
            assert "scope" in d, "missing scope"
            assert "evidence_ids" in d, "missing evidence_ids"

    def test_heuristic_draft_evidence_binding(self, real_topic_state):
        """Each draft's evidence_ids must reference existing evidence_contexts."""
        valid_ev_ids = {ctx["candidate_id"]
                        for ctx in real_topic_state["evidence_contexts"]}
        drafts = _heuristic_draft(real_topic_state)
        for d in drafts:
            bound = [eid for eid in d.get("evidence_ids", []) if eid in valid_ev_ids]
            assert len(bound) >= 1, \
                f"draft {d.get('candidate_id')} has 0 valid evidence bindings"

    def test_parse_draft_output_never_accepted(self, real_topic_state):
        """parse_draft_output should downgrade accepted to needs_evidence."""
        raw_llm_output = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "ViT对小缺陷检测不足",
                    "method": "引入CBAM+Fpn",
                    "insight": "注意力机制关注缺陷区域提高精度",
                    "scope": "钢材表面",
                    "evidence_ids": ["ev-vit-0", "ev-cbam-1", "ev-neu-2"],
                    "status": "accepted",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        drafts = parse_draft_output(raw_llm_output, real_topic_state)
        assert len(drafts) == 1
        assert drafts[0]["status"] == "needs_evidence", \
            "accepted should be downgraded to needs_evidence"

    def test_parse_draft_output_draft_preserved(self, real_topic_state):
        """draft status with >=3 evidence_ids preserved as draft."""
        raw_llm_output = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "ViT对小缺陷检测不足",
                    "method": "引入CBAM+FPN",
                    "insight": "小缺陷检测精度预期提升",
                    "scope": "钢材表面缺陷检测",
                    "evidence_ids": ["ev-vit-0", "ev-cbam-1", "ev-neu-2"],
                    "status": "draft",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        drafts = parse_draft_output(raw_llm_output, real_topic_state)
        assert len(drafts) == 1
        assert drafts[0]["status"] == "draft", \
            "draft with sufficient evidence should stay draft"

    def test_parse_draft_output_needs_evidence_when_lacking(self, real_topic_state):
        """needs_evidence with <3 evidence_ids preserved."""
        raw_llm_output = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "gap description",
                    "method": "approach",
                    "insight": "finding",
                    "scope": "scope",
                    "evidence_ids": ["ev-vit-0"],
                    "status": "needs_evidence",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        drafts = parse_draft_output(raw_llm_output, real_topic_state)
        assert len(drafts) == 1
        assert drafts[0]["status"] == "needs_evidence"
        assert len(drafts[0]["evidence_ids"]) == 1

    def test_unbound_evidence_flagged(self, real_topic_state):
        """Evidence IDs not in evidence_contexts should be filtered and flagged."""
        raw_llm_output = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "gap",
                    "method": "method",
                    "insight": "insight",
                    "scope": "scope",
                    "evidence_ids": ["ev-vit-0", "fake-id-999"],
                    "status": "draft",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        drafts = parse_draft_output(raw_llm_output, real_topic_state)
        ev_ids = drafts[0]["evidence_ids"]
        assert "fake-id-999" not in ev_ids, "unbound ID should be filtered"
        assert "ev-vit-0" in ev_ids, "valid ID should remain"
        risks = drafts[0].get("pseudo_innovation_risks", [])
        assert any("unbound" in r for r in risks), "unbound evidence should be flagged"

    def test_novelty_draft_node_returns_trace(self, real_topic_state):
        """novelty_draft_node always returns trace_events."""
        with patch(
            "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
            side_effect=Exception("LLM unavailable — force heuristic"),
        ):
            result = novelty_draft_node(real_topic_state)
        assert "novelty_drafts" in result
        assert "trace_events" in result
        assert len(result["trace_events"]) == 1
        trace = result["trace_events"][0]
        assert trace["node"] == "novelty_draft"
        assert trace["provider"] == "heuristic"


# ══════════════════════════════════════════════════════════════════════
# 验收2: No-evidence fixture — not auto-accepted, Claim Judge blocks
# ══════════════════════════════════════════════════════════════════════

class TestAcceptanceNoEvidence:
    """验收2: 无证据 fixture 场景验证."""

    def test_no_evidence_never_accepted(self, no_evidence_state):
        """_heuristic_draft without evidence must produce needs_evidence."""
        drafts = _heuristic_draft(no_evidence_state)
        assert len(drafts) >= 1
        for d in drafts:
            assert d["status"] in ("draft", "needs_evidence"), \
                f"unexpected status={d['status']}"
            # Without evidence, heuristic produces needs_evidence
            if not d.get("evidence_ids"):
                assert d["status"] == "needs_evidence"

    def test_no_evidence_draft_has_risk_flag(self, no_evidence_state):
        """No-evidence drafts should have appropriate risk flags."""
        drafts = _heuristic_draft(no_evidence_state)
        for d in drafts:
            risks = d.get("pseudo_innovation_risks", [])
            relevant_flags = {"insufficient_evidence_binding", "no_innovation_extracted",
                              "validation_failed"}
            assert any(f in risks for f in relevant_flags), \
                f"no relevant risk flag in {risks}"

    def test_empty_innovation_returns_empty(self, empty_innovation_state):
        """novelty_draft_node with no innovation points returns empty."""
        result = novelty_draft_node(empty_innovation_state)
        assert result["novelty_drafts"] == []
        assert len(result["trace_events"]) == 1

    def test_claim_judge_rejects_no_evidence(self, no_evidence_state):
        """Claim Judge must reject or flag innovations without evidence binding."""
        from apps.api.app.services.agents.graph.nodes.claim_judge import (
            claim_judge_node,
        )

        mock_llm_response = {
            "judgements": [
                {
                    "candidate_id": "nd-001",
                    "pmi_valid": False,
                    "evidence_complete": False,
                    "differentiation_valid": False,
                    "first_claim_correctly_downgraded": False,
                    "falsifiability_defined": False,
                    "verdict": "REJECT",
                    "issues": ["missing evidence binding", "first claim unsupported",
                               "no adjacent work differentiation"],
                    "required_fixes": ["add evidence", "downgrade first claim"],
                }
            ],
            "overall_verdict": "REJECT",
            "blocked_items": ["nd-001: no evidence"],
            "summary": "all candidates rejected due to missing evidence",
        }
        with patch(
            "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
            return_value=mock_llm_response,
        ):
            state = dict(no_evidence_state)
            state["innovation_points"] = no_evidence_state["innovation_points"]
            state["novelty_drafts"] = _heuristic_draft(no_evidence_state)
            result = claim_judge_node(state)
        assert result["claim_judge_verdict"] == "REJECT", \
            "Claim Judge should reject without evidence"
        assert len(result["claim_judgements"]) >= 1
        assert all(j.get("verdict") in ("REJECT", "REVISE")
                   for j in result["claim_judgements"]), \
            "all judgements should be non-ACCEPT without evidence"

    def test_claim_judge_blocks_first_claim(self, no_evidence_state):
        """First claim (首次/开创性) without evidence must be blocked."""
        from apps.api.app.services.agents.graph.nodes.claim_judge import (
            claim_judge_node,
        )

        mock_llm_response = {
            "judgements": [
                {
                    "candidate_id": "nd-001",
                    "pmi_valid": True,
                    "evidence_complete": False,
                    "differentiation_valid": False,
                    "first_claim_correctly_downgraded": True,
                    "falsifiability_defined": False,
                    "verdict": "REVISE",
                    "issues": ["first claim without literature verification",
                               "no support/refute/test conditions"],
                    "required_fixes": ["needs_literature_verification",
                                       "add falsifiable conditions"],
                }
            ],
            "overall_verdict": "REVISE",
            "blocked_items": ["nd-001: needs literature verification"],
            "summary": "first claim needs literature verification",
        }
        with patch(
            "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
            return_value=mock_llm_response,
        ):
            state = dict(no_evidence_state)
            state["innovation_points"] = no_evidence_state["innovation_points"]
            state["novelty_drafts"] = _heuristic_draft(no_evidence_state)
            result = claim_judge_node(state)
        assert result["claim_judge_verdict"] in ("REVISE", "REJECT"), \
            "first claim without evidence should be revise or reject"
        assert len(result.get("blocked_items", [])) >= 1, \
            "blocked_items should identify the issue"

    def test_claim_judge_empty_innovation(self):
        """Claim Judge with no innovation points returns REJECT."""
        from apps.api.app.services.agents.graph.nodes.claim_judge import (
            claim_judge_node,
        )
        result = claim_judge_node({
            "topic": "test",
            "innovation_points": [],
            "evidence_contexts": [],
        })
        assert result["claim_judge_verdict"] == "REJECT"
        assert result["claim_judgements"] == []


# ══════════════════════════════════════════════════════════════════════
# Schema-level acceptance (NoveltyCandidate model)
# ══════════════════════════════════════════════════════════════════════

class TestNoveltySchemaAcceptance:
    """NoveltyCandidate schema enforcement of acceptance rules."""

    def test_first_claim_auto_downgraded(self):
        """First claim markers force needs_literature_verification."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import (
            NoveltyCandidate,
        )
        candidate = NoveltyCandidate(
            candidate_id="nd-001",
            problem="首次提出基于拓扑纠错的加速器",
            method="拓扑编码方法",
            insight="预期性能提升10倍",
            evidence_ids=["ev-0", "ev-1", "ev-2"],
            status="draft",
        )
        assert candidate.status == "needs_literature_verification"
        assert "first_claim_unsupported" in candidate.pseudo_innovation_risks

    def test_accepted_requires_3_evidence(self):
        """accepted status with <3 evidence_ids raises ValueError."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import (
            NoveltyCandidate,
        )
        with pytest.raises(ValueError, match="at least 3 evidence_ids"):
            NoveltyCandidate(
                candidate_id="nd-001",
                problem="gap",
                method="method",
                insight="insight",
                evidence_ids=["ev-0"],
                status="accepted",
            )

    def test_accepted_with_3_evidence_ok(self):
        """accepted with >=3 evidence_ids is valid."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import (
            NoveltyCandidate,
        )
        candidate = NoveltyCandidate(
            candidate_id="nd-001",
            problem="specific gap",
            method="concrete method",
            insight="conditional finding",
            evidence_ids=["ev-0", "ev-1", "ev-2"],
            status="accepted",
        )
        assert candidate.status == "accepted"
        assert len(candidate.evidence_ids) >= 3

    def test_insight_performance_only_downgraded(self):
        """Insight with only metric claims downgraded to needs_evidence."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import (
            NoveltyCandidate,
        )
        candidate = NoveltyCandidate(
            candidate_id="nd-001",
            problem="gap",
            method="method",
            insight="accuracy达到95%, F1提高了5%, outperforms SOTA",
            evidence_ids=["ev-0", "ev-1", "ev-2"],
            status="draft",
        )
        assert candidate.status == "needs_evidence", \
            "performance-only insight should be downgraded"
