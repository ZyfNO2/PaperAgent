"""Session 62 M6: DirectionDecisionReport — aggregate M1-M5 output.

ponytail: 单纯 orchestration, 不加新逻辑; 选定 recommended_direction_id 规则清晰。
"""
from __future__ import annotations

from datetime import datetime, timezone

from .direction_planner import GraduationDirection, plan_directions
from .risk_scorer import score_direction
from .evidence_bundle import build_evidence_bundle
from .baseline_advisor import recommend_baselines
from .module_extension_advisor import recommend_modules
from ...schemas_graduation_direction import (
    DirectionDecisionReport,
    GraduationDirection as GraduationDirectionOut,
    ScoringBreakdownItem,
    ExtensionModule as ExtensionModuleOut,
    BaselineRecommendation as BaselineRecommendationOut,
)


STOP_REASON = "已生成方向与 baseline 建议, 等待用户确认方向, 不生成开题报告"


def _baseline_to_pydantic(b) -> BaselineRecommendationOut:
    return BaselineRecommendationOut(
        name=b.name,
        rationale=b.rationale,
        required_data=b.required_data,
        reproducibility=b.reproducibility,
        estimated_compute=b.estimated_compute,
        risks=list(b.risks),
    )


def _module_to_pydantic(m) -> ExtensionModuleOut:
    return ExtensionModuleOut(
        name=m.name,
        attach_to=m.attach_to,
        problem_solved=m.problem_solved,
        ablation_plan=m.ablation_plan,
        effort=m.effort,
        risks=list(m.risks),
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_recommended(directions: list[GraduationDirection]) -> str:
    """推荐: 评分最高; 平局取 fallback_route 非空者."""
    if not directions:
        return ""

    def _key(d: GraduationDirection) -> tuple[int, int, int]:
        # sort key: (has_fallback, idx) — placeholder, real scoring happens below
        return (1 if d.fallback_route else 0, 0)

    return directions[0].direction_id  # post-scoring 时会覆盖


def _to_output(
    d: GraduationDirection,
    *,
    has_paper: bool,
    has_dataset: bool,
    has_repo: bool,
    has_local_rag: bool,
) -> GraduationDirectionOut:
    breakdown = score_direction(
        d,
        has_paper=has_paper,
        has_dataset=has_dataset,
        has_repo=has_repo,
        has_local_rag=has_local_rag,
    )
    baselines = recommend_baselines(d, has_dataset=has_dataset, max_n=3)
    mods = recommend_modules(d, baselines, max_n=4)

    return GraduationDirectionOut(
        direction_id=d.direction_id,
        title=d.title,
        research_object=d.research_object,
        task=d.task,
        method_route=d.method_route,
        why_graduation_friendly=list(d.why_graduation_friendly),
        fallback_route=d.fallback_route,
        score=breakdown.score,
        risk_level=breakdown.risk_level,
        recommended_baselines=[_baseline_to_pydantic(b) for b in baselines],
        extension_modules=[_module_to_pydantic(m) for m in mods],
        scoring_breakdown=[
            ScoringBreakdownItem(
                key=item["key"],
                label=item["label"],
                score=item["score"],
                weight=item["weight"],
                note=item["note"],
            ) for item in breakdown.items
        ],
    )


def build_decision_report(
    project_id: str,
    topic: str,
    *,
    keywords: list[str] | None = None,
    use_last_retrieval: bool = True,
    use_local_rag: bool = True,
    local_rag_query: str | None = None,
    max_directions: int = 3,
) -> DirectionDecisionReport:
    """端到端: plan → score → bundle → baseline → module → report.

    ponytail: 不暴露中间 dataclass 给前端, 全部走 pydantic model.
    """

    if not topic or not topic.strip():
        raise ValueError("topic 不能为空")

    # 1) 方向
    directions_in = plan_directions(topic, keywords=keywords, max_directions=max_directions)
    if not directions_in:
        raise ValueError("无法生成任何毕业方向, 请检查题目")

    # 2) 证据 (按方向共用同一份 bundle + 全局 evidence_flags)
    bundle, counts = build_evidence_bundle(
        project_id,
        use_last_retrieval=use_last_retrieval,
        use_local_rag=use_local_rag,
        local_rag_query=local_rag_query or topic,
    )

    has_paper = counts["paper"] > 0
    has_dataset = counts["dataset"] > 0
    has_repo = counts["repo"] > 0
    has_local_rag = counts["rag_ref"] > 0

    # 3) 输出方向
    directions_out: list[GraduationDirectionOut] = []
    for d in directions_in:
        out = _to_output(
            d,
            has_paper=has_paper,
            has_dataset=has_dataset,
            has_repo=has_repo,
            has_local_rag=has_local_rag,
        )
        # 共享同一份 evidence_bundle (它对每个方向都反映当前证据)
        out.evidence_bundle = bundle
        directions_out.append(out)

    # 4) 选推荐 (评分最高; 平局取 fallback_route 非空者)
    directions_out.sort(
        key=lambda x: (
            x.score,
            1 if x.fallback_route else 0,
        ),
        reverse=True,
    )
    recommended_id = directions_out[0].direction_id if directions_out else ""

    # 5) 警告: 无任何证据时, 显式提示
    warnings: list[str] = []
    if not (has_paper or has_dataset or has_repo or has_local_rag):
        warnings.append("未找到任何证据候选, 当前方向仅供参考, 建议先补一轮检索")

    return DirectionDecisionReport(
        project_id=project_id,
        topic=topic,
        recommended_direction_id=recommended_id,
        directions=directions_out,
        stop_reason=STOP_REASON,
        generated_at=_utcnow_iso(),
        evidence_sources=counts,
        warnings=warnings,
    )


if __name__ == "__main__":
    # ponytail: self-check
    rpt = build_decision_report(
        "ot_test",
        "基于三维成像的损伤智能检测",
        keywords=["裂缝", "点云"],
        use_last_retrieval=True,
        use_local_rag=True,
        local_rag_query="裂缝检测",
        max_directions=3,
    )
    assert 2 <= len(rpt.directions) <= 3, len(rpt.directions)
    assert rpt.recommended_direction_id, rpt.recommended_direction_id
    assert rpt.stop_reason == STOP_REASON, rpt.stop_reason
    assert all(d.recommended_baselines for d in rpt.directions), rpt.directions
    assert all(2 <= len(d.extension_modules) <= 4 for d in rpt.directions), rpt.directions
    assert all(d.scoring_breakdown for d in rpt.directions), rpt.directions
    print(f"OK decision_report self-check (directions={len(rpt.directions)}, rec={rpt.recommended_direction_id})")