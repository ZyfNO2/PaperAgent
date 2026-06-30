"""Session 62 M6: DirectionDecisionReport — aggregate M1-M5 output.

ponytail: 单纯 orchestration, 不加新逻辑; 选定 recommended_direction_id 规则清晰。
"""
from __future__ import annotations

from datetime import datetime, timezone

from .direction_planner import GraduationDirection, plan_directions
from .risk_scorer import score_direction
from .evidence_bundle import build_evidence_bundle
from .baseline_advisor import recommend_baselines, BaselineRecommendation
from .module_extension_advisor import recommend_modules, ExtensionModule
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


def _llm_baselines_to_dataclass(items: list[dict] | None) -> list[BaselineRecommendation] | None:
    """把 LLM 返回的 baseline dict 列表转 dataclass (供 _to_output 优先消费)."""
    if not items:
        return None
    from .baseline_advisor import BaselineRecommendation as _BR
    out: list[_BR] = []
    for b in items[:3]:
        if not isinstance(b, dict) or not b.get("name"):
            continue
        out.append(_BR(
            name=str(b["name"]),
            rationale=str(b.get("rationale") or ""),
            required_data=str(b.get("required_data") or ""),
            reproducibility=str(b.get("reproducibility") or "medium"),
            estimated_compute=str(b.get("estimated_compute") or ""),
            risks=list(b.get("risks") or []),
        ))
    return out or None


def _llm_modules_to_dataclass(items: list[dict] | None) -> list[ExtensionModule] | None:
    if not items:
        return None
    from .module_extension_advisor import ExtensionModule as _EM
    out: list[_EM] = []
    for m in items[:4]:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        effort = str(m.get("effort") or "M")
        if effort not in ("S", "M", "L"):
            effort = "M"
        out.append(_EM(
            name=str(m["name"]),
            attach_to=str(m.get("attach_to") or ""),
            problem_solved=str(m.get("problem_solved") or ""),
            ablation_plan=str(m.get("ablation_plan") or ""),
            effort=effort,
            risks=list(m.get("risks") or []),
        ))
    return out or None


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
    llm_baselines: list[BaselineRecommendation] | None = None,
    llm_modules: list[ExtensionModule] | None = None,
) -> GraduationDirectionOut:
    breakdown = score_direction(
        d,
        has_paper=has_paper,
        has_dataset=has_dataset,
        has_repo=has_repo,
        has_local_rag=has_local_rag,
    )
    # ponytail: 优先用 LLM 提供的 baseline + module (LLM 路径读懂题目,
    # 不会硬塞 YOLO/U-Net). 仅在 LLM 未提供时才走 M4/M5 任务路径启发式.
    if llm_baselines:
        baselines = llm_baselines[:3]
    else:
        baselines = recommend_baselines(d, has_dataset=has_dataset, max_n=3)
    if llm_modules:
        mods = llm_modules[:4]
    else:
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
    use_last_retrieval: bool = True,
    use_local_rag: bool = True,
    local_rag_query: str | None = None,
    max_directions: int = 3,
    prefer: str = "auto",
) -> DirectionDecisionReport:
    """端到端: plan (LLM) → score → bundle → baseline (LLM 优先) → module (LLM 优先) → report.

    ponytail:
    - plan 失败 → 直接抛 DirectionPlannerError (fail-fast, 不做物理分词 fallback)
    - LLM 给的 baseline/module 优先于 M4/M5 启发式 (避免 M4 把 3D 题硬塞 YOLO/U-Net)
    - DirectorResult.source + arxiv_refs 通过 evidence_sources 暴露给前端调试
    """

    if not topic or not topic.strip():
        raise ValueError("topic 不能为空")

    # 1) 方向 (LLM-first, 失败抛 DirectionPlannerError)
    directions_in, director_info = plan_directions(topic, max_directions=max_directions, prefer=prefer)

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

    # 3) 输出方向 (LLM 给的 baseline/module 优先)
    directions_out: list[GraduationDirectionOut] = []
    for d in directions_in:
        llm_b = _llm_baselines_to_dataclass(getattr(d, "_llm_baselines", None))
        llm_m = _llm_modules_to_dataclass(getattr(d, "_llm_modules", None))
        out = _to_output(
            d,
            has_paper=has_paper,
            has_dataset=has_dataset,
            has_repo=has_repo,
            has_local_rag=has_local_rag,
            llm_baselines=llm_b,
            llm_modules=llm_m,
        )
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
    warnings.append(f"方向生成来源: {director_info.source} (arxiv_refs={len(director_info.arxiv_refs)})")

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