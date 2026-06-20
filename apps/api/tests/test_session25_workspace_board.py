"""Session 25: Workspace Board backend tests.

覆盖 SOP §6 S25-B-1~8:
1. Candidate 可加入 Selected
2. 重复加入同一 Candidate 幂等
3. Selected 可移除
4. mark_core 只改变 selected 状态
5. Selected 不含 support_level
6. Selected 不写 Evidence
7. coverage summary 计算正确
8. S24 Candidate schema 不回退
"""

from __future__ import annotations

import pytest

from app.schemas_workspace import (
    CoverageSummary,
    SelectedResource,
    WorkspaceActionRequest,
    WorkspaceActionResult,
    WorkspaceBoard,
    add_to_selected,
    compute_coverage,
    mark_core,
    mark_needs_review,
    remove_from_selected,
)


# ---------- S25-B-1: Candidate 可加入 Selected ---------- #


class TestAddToSelected:
    def test_add_returns_selected_id(self):
        board = WorkspaceBoard()
        result = add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper", candidate_kind="paper")
        assert result.ok is True
        assert result.selected_id is not None
        assert len(board.selected_resources) == 1

    def test_selected_has_candidate_reference(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper", candidate_kind="paper")
        sel = board.get_selected("cand_001")
        assert sel is not None
        assert sel.candidate_id == "cand_001"
        assert sel.kind == "paper"

    def test_selected_default_status(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001")
        sel = board.get_selected("cand_001")
        assert sel.verification_status == "unchecked"
        assert sel.evidence_status == "not_promoted"
        assert sel.is_core is False
        assert sel.needs_review is False


# ---------- S25-B-2: 重复加入同一 Candidate 幂等 ---------- #


class TestIdempotentAdd:
    def test_idempotent_add_same_candidate(self):
        board = WorkspaceBoard()
        r1 = add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper")
        r2 = add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper")
        assert r1.selected_id == r2.selected_id
        assert len(board.selected_resources) == 1

    def test_idempotent_message(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001")
        r2 = add_to_selected(board, candidate_id="cand_001")
        assert "idempotent" in r2.message.lower() or "already" in r2.message.lower()


# ---------- S25-B-3: Selected 可移除 ---------- #


class TestRemoveFromSelected:
    def test_remove_existing(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper")
        result = remove_from_selected(board, candidate_id="cand_001")
        assert result.ok is True
        assert len(board.selected_resources) == 0

    def test_remove_nonexistent(self):
        board = WorkspaceBoard()
        result = remove_from_selected(board, candidate_id="cand_nonexistent")
        assert result.ok is False

    def test_remove_does_not_affect_other_candidates(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Paper A")
        add_to_selected(board, candidate_id="cand_002", candidate_title="Paper B")
        remove_from_selected(board, candidate_id="cand_001")
        assert len(board.selected_resources) == 1
        assert board.selected_resources[0].candidate_id == "cand_002"


# ---------- S25-B-4: mark_core 只改变 selected 状态 ---------- #


class TestMarkCore:
    def test_mark_core(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Core Paper")
        result = mark_core(board, candidate_id="cand_001", core=True)
        assert result.ok is True
        sel = board.get_selected("cand_001")
        assert sel.is_core is True

    def test_unmark_core(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Paper")
        mark_core(board, candidate_id="cand_001", core=True)
        mark_core(board, candidate_id="cand_001", core=False)
        assert board.get_selected("cand_001").is_core is False

    def test_mark_core_not_selected(self):
        board = WorkspaceBoard()
        result = mark_core(board, candidate_id="cand_nonexistent")
        assert result.ok is False


# ---------- S25-B-5: Selected 不含 support_level ---------- #


class TestSelectedNoSupportLevel:
    def test_selected_no_support_level_field(self):
        sel = SelectedResource(
            selected_id="sel_001",
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert not hasattr(sel, "support_level") or sel.model_fields.get("support_level") is None


# ---------- S25-B-6: Selected 不写 Evidence ---------- #


class TestSelectedNoEvidence:
    def test_selected_not_evidence(self):
        sel = SelectedResource(
            selected_id="sel_001",
            candidate_id="cand_001",
            kind="paper",
            title="Test Paper",
        )
        assert sel.evidence_status == "not_promoted"
        assert sel.verification_status == "unchecked"

    def test_add_to_selected_no_evidence_created(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="cand_001", candidate_title="Test Paper")
        # Evidence 不应自动创建
        for sel in board.selected_resources:
            assert sel.evidence_status == "not_promoted"


# ---------- S25-B-7: coverage summary 计算正确 ---------- #


class TestCoverageSummary:
    def test_empty_board_coverage(self):
        board = WorkspaceBoard()
        cov = compute_coverage(board)
        assert cov.total_selected == 0
        assert cov.has_dataset is False
        assert cov.has_baseline is False

    def test_coverage_with_mixed_types(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="c1", candidate_kind="paper", candidate_title="Paper A")
        add_to_selected(board, candidate_id="c2", candidate_kind="paper", candidate_title="Paper B")
        add_to_selected(board, candidate_id="c3", candidate_kind="dataset", candidate_title="Dataset A")
        add_to_selected(board, candidate_id="c4", candidate_kind="repo", candidate_title="Repo A")
        cov = compute_coverage(board)
        assert cov.selected_paper_count == 2
        assert cov.selected_dataset_count == 1
        assert cov.selected_repo_count == 1
        assert cov.has_dataset is True
        assert cov.has_baseline is True
        assert cov.total_selected == 4

    def test_coverage_needs_review(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="c1", candidate_kind="paper", candidate_title="Paper")
        mark_needs_review(board, candidate_id="c1", needs=True)
        cov = compute_coverage(board)
        assert cov.has_needs_review is True

    def test_coverage_unverified_url(self):
        board = WorkspaceBoard()
        add_to_selected(board, candidate_id="c1", candidate_kind="paper", candidate_title="Paper")
        cov = compute_coverage(board)
        assert cov.has_url_unverified is True


# ---------- S25-B-8: S24 Candidate schema 不回退 ---------- #


class TestS24NoRegression:
    def test_candidate_imports(self):
        from app.schemas_candidates import (
            CandidateActionRequest,
            CandidateList,
            CandidateResource,
            QueryPlan,
            candidate_is_not_evidence,
        )
        cand = CandidateResource(candidate_id="cand_001", kind="paper", title="Test")
        assert candidate_is_not_evidence(cand) is True

    def test_blocked_response_imports(self):
        from app.schemas_candidates import BlockedResponse
        resp = BlockedResponse()
        assert resp.blocked is True
