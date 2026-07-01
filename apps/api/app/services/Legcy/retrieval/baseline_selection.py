"""Session 65 T2: 用户手动选 baseline.

硬规则:
- 系统绝不自动选 baseline.
- Survey / Irrelevant / Dataset 类候选不能作 baseline.
- 必须用户显式触发 select_baseline() (前端点"设为 Baseline").
- 未选时 status=pending_selection, 选过至少一个为 baseline_selected,
  把已选的全部移除后回到 pending_selection.

存储: 内存 dict, project_id -> BaselineSelectionState.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .candidate_actions import _find_candidate  # 复用候选定位


# ---------- 模型 ---------- #


BaselineRole = Literal["primary", "secondary", "comparison"]


class BaselineSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    baseline_role: BaselineRole
    user_reason: str
    expected_dataset: str | None = None
    selected_at: str  # ISO timestamp


class BaselineSelectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    selected_baselines: list[BaselineSelection] = Field(default_factory=list)
    status: Literal["pending_selection", "baseline_selected", "baseline_rejected"] = "pending_selection"


# ---------- 内存存储 ---------- #


_STATE: dict[str, BaselineSelectionState] = {}
_LOCK = threading.Lock()


# ---------- 角色判断 ---------- #


def can_be_baseline(candidate: dict) -> bool:
    """候选能否作 baseline.

    不能: survey / irrelevant / dataset_paper / candidate_type='dataset'.
    可以: baseline_framework / baseline_method / parallel_application_paper /
          module_improvement_paper / 其余有意义的 paper 或 repo.
    """

    role = (candidate.get("literature_role") or "").strip()
    ctype = (candidate.get("candidate_type") or "").strip()

    if ctype == "dataset":
        return False
    if role in {"survey", "irrelevant", "dataset_paper"}:
        return False

    # 没分到明确角色的 paper / repo, 留个口子 (用户可显式选, 由 UI 提示)
    return True


# ---------- 核心函数 ---------- #


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit_trace(project_id: str, action: str, **payload: Any) -> None:
    """复用 S61 风格的 trace 日志, 直接 print 到 stdout."""

    try:
        from .orchestrator import emit_run_event  # type: ignore[attr-defined]
        emit_run_event(project_id=project_id, action=action, **payload)
        return
    except Exception:
        pass

    # ponytail: fallback 到简单 print, orchestrator 没接 trace 也能跑
    print(f"[baseline_selection] project={project_id} action={action} payload={payload}")


def select_baseline(
    project_id: str,
    candidate: dict,
    role: str,
    user_reason: str,
    expected_dataset: str | None = None,
) -> BaselineSelection:
    """用户选 baseline. 覆盖同 candidate_id 的旧选择."""

    if role not in ("primary", "secondary", "comparison"):
        raise ValueError(f"非法 baseline_role: {role!r}")

    candidate_id = candidate.get("candidate_id") or ""
    if not candidate_id:
        raise ValueError("candidate.candidate_id 必填")

    if not can_be_baseline(candidate):
        cand, _ = _find_candidate(project_id, candidate_id)
        actual_role = (cand.raw or {}).get("literature_role") if cand else None
        # ponytail: 错误信息带上真实角色, 方便 UI 提示
        raise ValueError(
            f"该候选不可作 baseline (role={actual_role or candidate.get('literature_role') or 'unknown'}, "
            f"type={candidate.get('candidate_type')})"
        )

    if not (user_reason or "").strip():
        raise ValueError("user_reason 必填 (用户必须给出选它的理由)")

    sel = BaselineSelection(
        candidate_id=candidate_id,
        baseline_role=role,
        user_reason=user_reason.strip(),
        expected_dataset=expected_dataset,
        selected_at=_now_iso(),
    )

    with _LOCK:
        state = _STATE.get(project_id) or BaselineSelectionState(project_id=project_id)
        state.selected_baselines = [
            s for s in state.selected_baselines if s.candidate_id != candidate_id
        ]
        state.selected_baselines.append(sel)
        state.status = "baseline_selected"
        _STATE[project_id] = state

    _emit_trace(
        project_id,
        "baseline_selected",
        candidate_id=candidate_id,
        baseline_role=role,
        expected_dataset=expected_dataset,
        reason=user_reason.strip(),
    )

    return sel


def unselect_baseline(project_id: str, candidate_id: str) -> None:
    """移除指定 candidate_id 的 baseline 标记."""

    with _LOCK:
        state = _STATE.get(project_id)
        if state is None:
            return
        before = len(state.selected_baselines)
        state.selected_baselines = [
            s for s in state.selected_baselines if s.candidate_id != candidate_id
        ]
        if len(state.selected_baselines) == 0:
            state.status = "pending_selection"
        _STATE[project_id] = state

    _emit_trace(
        project_id,
        "baseline_unselected",
        candidate_id=candidate_id,
        remaining=len(state.selected_baselines) if state else 0,
        removed=(before - len(state.selected_baselines)) if state else 0,
    )


def get_selected_baselines(project_id: str) -> list[BaselineSelection]:
    with _LOCK:
        state = _STATE.get(project_id)
    return list(state.selected_baselines) if state else []


def get_baseline_state(project_id: str) -> BaselineSelectionState:
    with _LOCK:
        state = _STATE.get(project_id)
    return state or BaselineSelectionState(project_id=project_id)


def reset_baseline_state() -> None:
    """测试 / 自检用."""

    with _LOCK:
        _STATE.clear()


# ---------- 候选反查 (给 UI 用) ---------- #


def find_candidate_for_baseline(project_id: str, candidate_id: str):
    """复用 candidate_actions 的定位, 拿候选给 can_be_baseline 判."""

    return _find_candidate(project_id, candidate_id)


__all__ = [
    "BaselineRole",
    "BaselineSelection",
    "BaselineSelectionState",
    "can_be_baseline",
    "select_baseline",
    "unselect_baseline",
    "get_selected_baselines",
    "get_baseline_state",
    "find_candidate_for_baseline",
    "reset_baseline_state",
]


# ---------- self-check ---------- #


def _self_check() -> None:
    """最小可运行检查: 覆盖 select / unselect / 拒绝非法角色 / 拒绝 dataset."""

    from .literature_role_classifier import Role  # noqa: F401
    from . import orchestrator as _orch
    from ...schemas_retrieval import (
        QueryPlan,
        QueryPlanLayer,
        RetrievalCandidate,
        RetrievalRun,
        SourceResult,
    )

    # 清理
    reset_baseline_state()
    try:
        _orch.reset_retrieval_state()
    except Exception:
        pass

    plan = QueryPlan(
        project_id="proj_baseline_self_check",
        raw_topic="self check",
        paper_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
        dataset_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
        repo_queries=[QueryPlanLayer(layer="L1", queries=["t"])],
    )

    # 准备候选: 1 个 survey, 1 个 dataset, 1 个 baseline_method, 1 个 baseline_framework
    c_survey = RetrievalCandidate(
        candidate_id="c_survey",
        project_id="proj_baseline_self_check",
        candidate_type="paper",
        source="arxiv",
        title="A Survey on X",
        url="https://arxiv.org/abs/0000.0001",
    )
    c_dataset = RetrievalCandidate(
        candidate_id="c_dataset",
        project_id="proj_baseline_self_check",
        candidate_type="dataset",
        source="huggingface",
        title="X-Bench Dataset",
        url="https://huggingface.co/datasets/x",
    )
    c_method = RetrievalCandidate(
        candidate_id="c_method",
        project_id="proj_baseline_self_check",
        candidate_type="paper",
        source="arxiv",
        title="Novel Method for X",
        url="https://arxiv.org/abs/0000.0002",
    )
    c_fw = RetrievalCandidate(
        candidate_id="c_fw",
        project_id="proj_baseline_self_check",
        candidate_type="repo",
        source="github",
        title="YOLOv8",
        url="https://github.com/ultralytics/yolov8",
        repo_full_name="ultralytics/yolov8",
    )
    run = RetrievalRun(
        run_id="ret_baseline_selfcheck",
        project_id="proj_baseline_self_check",
        query_plan=plan,
        sources=["arxiv", "github", "huggingface"],
        source_results=[
            SourceResult(source="arxiv", status="completed", candidate_count=2),
            SourceResult(source="github", status="completed", candidate_count=1),
            SourceResult(source="huggingface", status="completed", candidate_count=1),
        ],
        started_at=_now_iso(),
        finished_at=_now_iso(),
        status="completed",
        total_candidates=4,
        candidates=[c_survey, c_dataset, c_method, c_fw],
    )
    with _orch._LOCK:
        _orch._RUNS["proj_baseline_self_check"] = [run]

    # 1) survey 不可选
    assert can_be_baseline({"candidate_type": "paper", "literature_role": "survey"}) is False
    assert can_be_baseline({"candidate_type": "paper", "literature_role": "irrelevant"}) is False
    assert can_be_baseline({"candidate_type": "dataset", "literature_role": "baseline_method"}) is False
    assert can_be_baseline({"candidate_type": "paper", "literature_role": "baseline_method"}) is True
    assert can_be_baseline({"candidate_type": "repo", "literature_role": "baseline_framework"}) is True

    # 2) 初始状态: pending
    st = get_baseline_state("proj_baseline_self_check")
    assert st.status == "pending_selection", st
    assert get_selected_baselines("proj_baseline_self_check") == []

    # 3) 拒绝 survey
    try:
        select_baseline(
            "proj_baseline_self_check",
            {"candidate_id": "c_survey", "candidate_type": "paper", "literature_role": "survey"},
            role="primary",
            user_reason="because",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("survey 应该被拒绝")

    # 4) 拒绝 dataset
    try:
        select_baseline(
            "proj_baseline_self_check",
            {"candidate_id": "c_dataset", "candidate_type": "dataset", "literature_role": "baseline_method"},
            role="primary",
            user_reason="because",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("dataset 应该被拒绝")

    # 5) 正常选 baseline_method
    sel1 = select_baseline(
        "proj_baseline_self_check",
        {"candidate_id": "c_method", "candidate_type": "paper", "literature_role": "baseline_method"},
        role="primary",
        user_reason="主流 baseline, 可复现",
        expected_dataset="X-Bench",
    )
    assert sel1.candidate_id == "c_method"
    assert sel1.baseline_role == "primary"
    assert sel1.expected_dataset == "X-Bench"

    st = get_baseline_state("proj_baseline_self_check")
    assert st.status == "baseline_selected", st
    assert len(st.selected_baselines) == 1

    # 6) 再选一个 secondary (framework)
    sel2 = select_baseline(
        "proj_baseline_self_check",
        {"candidate_id": "c_fw", "candidate_type": "repo", "literature_role": "baseline_framework"},
        role="secondary",
        user_reason="作为对比框架",
    )
    assert sel2.baseline_role == "secondary"

    st = get_baseline_state("proj_baseline_self_check")
    assert len(st.selected_baselines) == 2
    roles = sorted(s.baseline_role for s in st.selected_baselines)
    assert roles == ["primary", "secondary"], roles

    # 7) 同 candidate 再选: 覆盖 (id 唯一)
    select_baseline(
        "proj_baseline_self_check",
        {"candidate_id": "c_method", "candidate_type": "paper", "literature_role": "baseline_method"},
        role="comparison",
        user_reason="改角色为 comparison",
    )
    st = get_baseline_state("proj_baseline_self_check")
    assert len(st.selected_baselines) == 2
    method_sel = next(s for s in st.selected_baselines if s.candidate_id == "c_method")
    assert method_sel.baseline_role == "comparison", method_sel

    # 8) 拒空 reason
    try:
        select_baseline(
            "proj_baseline_self_check",
            {"candidate_id": "c_method", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="primary",
            user_reason="",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("空 user_reason 应该被拒绝")

    # 9) 拒非法 role
    try:
        select_baseline(
            "proj_baseline_self_check",
            {"candidate_id": "c_method", "candidate_type": "paper", "literature_role": "baseline_method"},
            role="quaternary",
            user_reason="r",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("非法 role 应该被拒绝")

    # 10) unselect 一个, 剩 1 个, 仍是 baseline_selected
    unselect_baseline("proj_baseline_self_check", "c_method")
    st = get_baseline_state("proj_baseline_self_check")
    assert len(st.selected_baselines) == 1
    assert st.status == "baseline_selected"

    # 11) 全部 unselect, 回到 pending_selection
    unselect_baseline("proj_baseline_self_check", "c_fw")
    st = get_baseline_state("proj_baseline_self_check")
    assert len(st.selected_baselines) == 0
    assert st.status == "pending_selection", st

    # 12) unselect 不存在的, no-op
    unselect_baseline("proj_baseline_self_check", "nonexistent")  # 不抛错

    print("[baseline_selection] self-check OK")


if __name__ == "__main__":
    _self_check()