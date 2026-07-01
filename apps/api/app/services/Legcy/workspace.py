"""双栏证据工作台服务 (Session 9 §4.2-§4.3).

把 evidence pool 按 type 拆成 3 个 board (paper / dataset / repo),
每个 board 分 4 栏: left=user_preferred, right=system_found+background, selected=core, rejected=rejected.
"""

from __future__ import annotations

from typing import Any

from ..schemas import EvidenceWorkspaceBoard, WorkspaceItemPatch, WorkspaceItemPatchResponse
from . import evidence as ev_store
from . import evidence as ev_trace


_BOARD_TYPE_BY_EVIDENCE_TYPE = {
    "paper": "paper",
    "dataset": "dataset",
    "repo": "repo",
}


def get_workspace_board(project_id: str) -> dict[str, EvidenceWorkspaceBoard]:
    """返回三类 board. 若 project 不存在, 返回空 board (不报错)."""

    proj = ev_store._get_project(project_id)
    boards: dict[str, EvidenceWorkspaceBoard] = {}
    by_type: dict[str, list[Any]] = {"paper": [], "dataset": [], "repo": []}
    for e in proj.items.values():
        if e.evidence_type in by_type:
            by_type[e.evidence_type].append(e)

    for btype, items in by_type.items():
        left, right, sel, rej = [], [], [], []
        for it in items:
            d = it.model_dump(mode="json")
            lane = d.get("workspace_lane", "system_found")
            rs = d.get("review_status", "pending")
            if lane == "rejected" or rs == "rejected":
                rej.append(d)
            elif lane == "selected" or rs == "core":
                sel.append(d)
            elif lane == "user_preferred":
                left.append(d)
            else:
                right.append(d)

        boards[btype] = EvidenceWorkspaceBoard(
            board_type=_BOARD_TYPE_BY_EVIDENCE_TYPE[btype],
            left_items=left,
            right_items=right,
            selected_items=sel,
            rejected_items=rej,
        )
    return boards


def patch_workspace_item(project_id: str, body: WorkspaceItemPatch) -> WorkspaceItemPatchResponse:
    """更新 evidence 的 workspace_lane (可选同步 review_status) + 写 Trace."""

    with ev_store._LEDGER_LOCK:
        proj = ev_store._get_project(project_id)
        if body.evidence_id not in proj.items:
            return WorkspaceItemPatchResponse(
                ok=False,
                evidence_id=body.evidence_id,
                workspace_lane="",
                review_status="",
                message=f"evidence_id {body.evidence_id} 不存在",
            )
        old = proj.items[body.evidence_id]
        new_data = old.model_dump()
        if body.workspace_lane is not None:
            new_data["workspace_lane"] = body.workspace_lane
        if body.review_status is not None:
            new_data["review_status"] = body.review_status
        # 联动: review_status 变化时同步 lane
        new_data["workspace_lane"] = ev_store._derive_workspace_lane(
            new_data.get("review_status", "pending"),
            new_data.get("workspace_lane", "system_found"),
        )
        proj.items[body.evidence_id] = ev_store.EvidenceItem(**new_data)
        updated = proj.items[body.evidence_id]

    # 写 Trace
    trace_event = ev_trace.append_trace(
        project_id,
        action="workspace_patch",
        target_type="workspace_item",
        target_id=body.evidence_id,
        evidence_id=body.evidence_id,
        reason=body.reason or f"lane={updated.workspace_lane} status={updated.review_status}",
        actor="user",
    )

    return WorkspaceItemPatchResponse(
        ok=True,
        evidence_id=body.evidence_id,
        workspace_lane=updated.workspace_lane,
        review_status=updated.review_status,
        message=f"已更新 lane={updated.workspace_lane}, status={updated.review_status}",
        trace_event=trace_event,
    )