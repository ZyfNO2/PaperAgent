"""Session 62 API: GraduationDirection planning endpoint.

POST /api/v1/projects/{project_id}/graduation-direction/plan
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...schemas_graduation_direction import (
    DirectionDecisionReport,
    GraduationDirectionRequest,
)
from ...services.graduation import build_decision_report
from ...services import evidence as ev_store

router = APIRouter(prefix="/api/v1/projects", tags=["graduation-direction"])


@router.post(
    "/{project_id}/graduation-direction/plan",
    response_model=DirectionDecisionReport,
    summary="Session 62: 生成毕业友好方向推荐 + baseline + 可加模块决策包",
)
def plan_graduation_direction(
    project_id: str,
    body: GraduationDirectionRequest,
) -> DirectionDecisionReport:
    """Session 62 §6.

    要求: 项目必须先跑过 OneTopic analyze 或 retrieval/search, 否则 evidence_sources 全 0.
    """

    # ponytail: 不强依赖 snapshot; 但提示用户先跑 analyze (避免空证据)
    snapshot = ev_store.get_snapshot(project_id)
    # snapshot=None 时, evidence_bundle 仍可生成 (只是全空); 不阻塞.

    try:
        report = build_decision_report(
            project_id=project_id,
            topic=body.topic,
            keywords=None,  # 当前用 topic 内嵌关键词; 后续可扩展
            use_last_retrieval=body.use_last_retrieval,
            use_local_rag=body.use_local_rag,
            local_rag_query=body.topic,
            max_directions=body.max_directions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return report