"""Session 65 T2: baseline_selection.py 测试."""

from __future__ import annotations

import pytest

from app.services.retrieval.baseline_selection import (
    can_be_baseline,
    get_baseline_state,
    get_selected_baselines,
    reset_baseline_state,
    select_baseline,
    unselect_baseline,
)
from app.services.retrieval.literature_role_classifier import Role  # noqa: F401


@pytest.fixture(autouse=True)
def _clean_state():
    reset_baseline_state()
    yield
    reset_baseline_state()


# ---------- can_be_baseline ---------- #


class TestCanBeBaseline:
    def test_survey_rejected(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "survey"}) is False

    def test_irrelevant_rejected(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "irrelevant"}) is False

    def test_dataset_paper_rejected(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "dataset_paper"}) is False

    def test_dataset_candidate_type_rejected(self):
        assert can_be_baseline({"candidate_type": "dataset", "literature_role": "baseline_method"}) is False

    def test_baseline_method_paper_accepted(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "baseline_method"}) is True

    def test_baseline_framework_repo_accepted(self):
        assert can_be_baseline({"candidate_type": "repo", "literature_role": "baseline_framework"}) is True

    def test_parallel_application_accepted(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "parallel_application_paper"}) is True

    def test_module_improvement_accepted(self):
        assert can_be_baseline({"candidate_type": "paper", "literature_role": "module_improvement_paper"}) is True

    def test_unknown_role_falls_through(self):
        # 没分到明确角色, 默认允许 (UI 层会提示)
        assert can_be_baseline({"candidate_type": "paper", "literature_role": ""}) is True
        assert can_be_baseline({"candidate_type": "paper"}) is True


# ---------- select_baseline 拒绝路径 ---------- #


class TestSelectBaselineRejects:
    def test_survey_raises(self):
        with pytest.raises(ValueError, match="不可作 baseline"):
            select_baseline(
                "proj_a",
                {"candidate_id": "x", "candidate_type": "paper", "literature_role": "survey"},
                role="primary",
                user_reason="r",
            )

    def test_dataset_raises(self):
        with pytest.raises(ValueError, match="不可作 baseline"):
            select_baseline(
                "proj_a",
                {"candidate_id": "x", "candidate_type": "dataset", "literature_role": "baseline_method"},
                role="primary",
                user_reason="r",
            )

    def test_empty_user_reason_raises(self):
        with pytest.raises(ValueError, match="user_reason"):
            select_baseline(
                "proj_a",
                {"candidate_id": "x", "candidate_type": "paper", "literature_role": "baseline_method"},
                role="primary",
                user_reason="   ",
            )

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError, match="非法 baseline_role"):
            select_baseline(
                "proj_a",
                {"candidate_id": "x", "candidate_type": "paper", "literature_role": "baseline_method"},
                role="quaternary",
                user_reason="r",
            )

    def test_missing_candidate_id_raises(self):
        with pytest.raises(ValueError, match="candidate_id"):
            select_baseline(
                "proj_a",
                {"candidate_type": "paper", "literature_role": "baseline_method"},
                role="primary",
                user_reason="r",
            )


# ---------- select / unselect 流程 ---------- #


class TestSelectUnselectFlow:
    def test_initial_state_is_pending(self):
        st = get_baseline_state("proj_b")
        assert st.status == "pending_selection"
        assert st.selected_baselines == []

    def test_select_first_makes_status_selected(self):
        sel = select_baseline(
            "proj_b",
            {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="primary",
            user_reason="ok",
            expected_dataset="DS-X",
        )
        assert sel.candidate_id == "c1"
        assert sel.baseline_role == "primary"
        assert sel.expected_dataset == "DS-X"
        assert sel.selected_at  # ISO timestamp 非空

        st = get_baseline_state("proj_b")
        assert st.status == "baseline_selected"
        assert len(st.selected_baselines) == 1

    def test_select_multiple_keeps_distinct(self):
        select_baseline(
            "proj_b",
            {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="primary",
            user_reason="r1",
        )
        select_baseline(
            "proj_b",
            {"candidate_id": "c2", "candidate_type": "repo", "literature_role": "baseline_framework"},
            role="secondary",
            user_reason="r2",
        )
        st = get_baseline_state("proj_b")
        assert len(st.selected_baselines) == 2
        ids = {s.candidate_id for s in st.selected_baselines}
        assert ids == {"c1", "c2"}

    def test_reselect_same_candidate_overrides_role(self):
        select_baseline(
            "proj_b",
            {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="primary",
            user_reason="r1",
        )
        select_baseline(
            "proj_b",
            {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="comparison",
            user_reason="r2",
        )
        st = get_baseline_state("proj_b")
        assert len(st.selected_baselines) == 1
        assert st.selected_baselines[0].baseline_role == "comparison"
        assert st.selected_baselines[0].user_reason == "r2"

    def test_unselect_keeps_status_when_others_remain(self):
        select_baseline("proj_b", {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        select_baseline("proj_b", {"candidate_id": "c2", "candidate_type": "repo", "literature_role": "baseline_framework"}, "secondary", "r")
        unselect_baseline("proj_b", "c1")
        st = get_baseline_state("proj_b")
        assert len(st.selected_baselines) == 1
        assert st.selected_baselines[0].candidate_id == "c2"
        assert st.status == "baseline_selected"

    def test_unselect_all_reverts_to_pending(self):
        select_baseline("proj_b", {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        unselect_baseline("proj_b", "c1")
        st = get_baseline_state("proj_b")
        assert st.status == "pending_selection"
        assert st.selected_baselines == []

    def test_unselect_nonexistent_is_noop(self):
        # 不抛错, 不影响状态
        select_baseline("proj_b", {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        unselect_baseline("proj_b", "ghost")
        st = get_baseline_state("proj_b")
        assert len(st.selected_baselines) == 1
        assert st.status == "baseline_selected"

    def test_get_selected_baselines_returns_list(self):
        assert get_selected_baselines("proj_b") == []
        select_baseline("proj_b", {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        out = get_selected_baselines("proj_b")
        assert len(out) == 1
        assert out[0].candidate_id == "c1"

    def test_isolated_per_project(self):
        select_baseline("proj_x", {"candidate_id": "c1", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        select_baseline("proj_y", {"candidate_id": "c2", "candidate_type": "paper", "literature_role": "baseline_method"}, "primary", "r")
        assert len(get_selected_baselines("proj_x")) == 1
        assert len(get_selected_baselines("proj_y")) == 1
        assert get_selected_baselines("proj_x")[0].candidate_id == "c1"
        assert get_selected_baselines("proj_y")[0].candidate_id == "c2"