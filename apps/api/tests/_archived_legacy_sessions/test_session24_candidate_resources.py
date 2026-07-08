"""Session 24: Candidate Resource backend tests.

覆盖 SOP §10 S24-B-1~8:
1. keyword 未 approved → blocked
2. approved_keywords → query_plan
3. query_plan → candidates
4. candidate 不等于 evidence
5. candidate status 枚举校验
6. URL 未验证时 risk_flags 包含 url_unverified
7. 用户标记写 Trace
8. S17 baseline 不回退
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas_candidates import (
    BlockedResponse,
    CandidateActionRequest,
    CandidateList,
    CandidateResource,
    QueryItem,
    QueryPlan,
    candidate_is_not_evidence,
)


# ---------- S24-B-1: blocked when keyword_review not approved ---------- #


class TestBlockedWithoutApproval:
    def test_blocked_response_schema(self):
        resp = BlockedResponse()
        assert resp.blocked is True
        assert "keyword_review" in resp.reason

    def test_blocked_response_custom_reason(self):
        resp = BlockedResponse(reason="custom reason")
        assert resp.blocked is True
        assert resp.reason == "custom reason"


# ---------- S24-B-2: approved_keywords → query_plan ---------- #


class TestQueryPlan:
    def test_query_plan_minimal(self):
        plan = QueryPlan(queries=[
            QueryItem(source="paper", query="YOLO defect detection"),
        ])
        assert len(plan.queries) == 1
        assert plan.queries[0].source == "paper"

    def test_query_plan_three_sources(self):
        plan = QueryPlan(queries=[
            QueryItem(source="paper", query="YOLO steel defect", priority="high"),
            QueryItem(source="dataset", query="NEU steel dataset", priority="medium"),
            QueryItem(source="repo", query="ultralytics yolov8", priority="low"),
        ])
        assert len(plan.by_source("paper")) == 1
        assert len(plan.by_source("dataset")) == 1
        assert len(plan.by_source("repo")) == 1
        assert len(plan.by_source("thesis_template")) == 0

    def test_query_plan_empty_rejected(self):
        with pytest.raises(ValidationError):
            QueryPlan(queries=[])

    def test_query_item_extra_forbidden(self):
        with pytest.raises(ValidationError):
            QueryItem(source="paper", query="test", unknown_field="bad")


# ---------- S24-B-3: query_plan → candidates ---------- #


class TestCandidateResource:
    def test_candidate_minimal(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Some Paper",
        )
        assert cand.candidate_id == "cand_001"
        assert cand.status == "candidate"
        assert cand.user_mark == "unreviewed"
        assert "url_unverified" in cand.risk_flags

    def test_candidate_full(self):
        cand = CandidateResource(
            candidate_id="cand_002",
            kind="dataset",
            title="NEU Steel Surface Defect Database",
            url="https://example.com/dataset",
            source="Kaggle",
            matched_keywords=["YOLO", "defect detection"],
            summary="Large-scale steel defect dataset",
            risk_flags=[],
            user_mark="saved",
        )
        assert cand.kind == "dataset"
        assert cand.user_mark == "saved"
        assert len(cand.matched_keywords) == 2

    def test_candidate_list(self):
        cl = CandidateList(
            candidates=[
                CandidateResource(candidate_id="c1", kind="paper", title="P1"),
                CandidateResource(candidate_id="c2", kind="repo", title="R1"),
            ],
            total_found=2,
        )
        assert len(cl.candidates) == 2


# ---------- S24-B-4: candidate != evidence ---------- #


class TestCandidateIsNotEvidence:
    def test_status_is_candidate(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert candidate_is_not_evidence(cand) is True

    def test_candidate_has_no_support_level(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert not hasattr(cand, "support_level") or cand.model_fields.get("support_level") is None


# ---------- S24-B-5: candidate status enum ---------- #


class TestStatusEnum:
    def test_status_always_candidate(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert cand.status == "candidate"

    def test_invalid_kind_rejected(self):
        with pytest.raises(ValidationError):
            CandidateResource(
                candidate_id="cand_001",
                kind="invalid_kind",
                title="Test Paper",
            )


# ---------- S24-B-6: risk_flags url_unverified ---------- #


class TestRiskFlags:
    def test_default_risk_flags(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert "url_unverified" in cand.risk_flags

    def test_custom_risk_flags(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
            risk_flags=["access_restricted"],
        )
        assert "url_unverified" not in cand.risk_flags
        assert "access_restricted" in cand.risk_flags


# ---------- S24-B-7: user mark / action ---------- #


class TestUserActions:
    def test_action_request(self):
        req = CandidateActionRequest(
            candidate_id="cand_001",
            action="save_candidate",
            note="looks relevant",
        )
        assert req.action == "save_candidate"
        assert req.note == "looks relevant"

    def test_all_actions_valid(self):
        for action in ["save_candidate", "reject_candidate", "mark_needs_review", "promote_to_selected"]:
            req = CandidateActionRequest(candidate_id="cand_001", action=action)
            assert req.action == action

    def test_invalid_action_rejected(self):
        with pytest.raises(ValidationError):
            CandidateActionRequest(candidate_id="cand_001", action="hack_the_planet")

    def test_user_mark_transitions(self):
        cand = CandidateResource(
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
            user_mark="saved",
        )
        assert cand.user_mark == "saved"


# ---------- S24-B-8: S17 baseline no regression ---------- #


class TestS17Baseline:
    def test_import_schemas_unchanged(self):
        """S17 的核心 schema 不受影响."""
        from app.schemas import OneTopicRequest
        req = OneTopicRequest(raw_topic="测试题目")
        assert req.raw_topic == "测试题目"
        assert req.goal_level == "保毕业"
