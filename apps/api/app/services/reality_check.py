"""Session 45: RealityCheck service — 资源可达性四层 + 实验周期三档.

判断逻辑:
1. 资源层: 根据 evidence (数据集/baseline) + keywords (方法词) 判断
2. 实验周期: 根据资源层推断
3. 毕业风险: goal_level + cycle 查表
4. 融合降级: graduation_risk=high → verdict 降级
"""

from __future__ import annotations

from typing import Literal

from ..schemas import EvidenceSummary, KeywordBreakdown
from ..schemas_reality import (
    ExperimentCycle,
    GraduationRisk,
    RealityCheck,
    ResourceTier,
    get_cycle_matrix,
)

# 需要大算力的方法关键词
_HEAVY_COMPUTE_METHODS = {
    "大语言模型", "大模型", "llm", "gpt", "bert", "transformer",
    "diffusion", "扩散模型", "生成模型", "预训练",
}


def _is_heavy_compute(keywords: KeywordBreakdown) -> bool:
    """判断方法是否需要大算力."""
    for m in keywords.method_keywords:
        if m.lower() in _HEAVY_COMPUTE_METHODS:
            return True
    return False


def _is_niche(keywords: KeywordBreakdown, raw_topic: str) -> bool:
    """判断题目是否极小众 (无公开数据集 + 对象词罕见)."""
    # 简单启发: 如果 object_keywords 里有"自采"/"自定义"/"新型"等词
    niche_hints = {"自采", "自定义", "新型", "全新", "自建"}
    for obj in keywords.object_keywords:
        for hint in niche_hints:
            if hint in obj or hint in raw_topic:
                return True
    return False


def _determine_resource_tier(
    keywords: KeywordBreakdown,
    ev: EvidenceSummary,
    raw_topic: str,
) -> tuple[ResourceTier, str]:
    """判断资源可达性四层."""
    has_data = ev.has_public_dataset
    has_baseline = ev.has_repro_baseline
    heavy = _is_heavy_compute(keywords)
    niche = _is_niche(keywords, raw_topic)

    if not has_data and not has_baseline and niche:
        return "infeasible", "无公开数据集 + 无可复现 baseline + 题目对象极小众, 真做不到"

    if not has_data:
        if not has_baseline:
            return "self_collect_data", "无公开数据集且无可复现 baseline, 需自采数据并从零搭建"
        return "self_collect_data", "无公开数据集, 需自采数据集"

    if heavy:
        return "rent_compute", f"有公开数据集但方法 ({keywords.method_keywords[0] if keywords.method_keywords else '大模型'}) 需要大算力, 需租 GPU"

    if has_data and has_baseline:
        return "existing_env", "有公开数据集 + 可复现 baseline + 非大模型方法, 现有环境可做"

    return "rent_compute", "有公开数据集但 baseline 复现难度未知, 可能需额外算力"


def _determine_cycle(
    tier: ResourceTier,
    ev: EvidenceSummary,
) -> tuple[ExperimentCycle, str]:
    """根据资源层推断实验周期."""
    if tier == "existing_env":
        return "week", "现有环境 + 成熟方法, 一轮实验约一周"
    if tier == "rent_compute":
        return "month", "需租算力, 一轮实验约一个月 (含排队+训练+调试)"
    if tier == "self_collect_data":
        if ev.has_repro_baseline:
            return "month", "需自采数据但有 baseline, 数据采集+标注约一个月"
        return "year", "需自采数据且无 baseline, 采集+标注+复现约一年"
    # infeasible
    return "year", "条件不足, 即使投入一年也难以完成"


def _calc_score(tier: ResourceTier, cycle: ExperimentCycle) -> int:
    """计算现实约束评分."""
    score_map = {
        ("existing_env", "week"): 90,
        ("existing_env", "month"): 70,
        ("rent_compute", "month"): 55,
        ("rent_compute", "week"): 65,
        ("self_collect_data", "month"): 40,
        ("self_collect_data", "year"): 20,
        ("infeasible", "year"): 5,
    }
    return score_map.get((tier, cycle), 30)


def _gen_suggestion(
    tier: ResourceTier,
    cycle: ExperimentCycle,
    risk: GraduationRisk,
    goal_level: str,
) -> str:
    """生成建议."""
    if tier == "infeasible":
        return "当前条件不可行, 建议更换研究对象到成熟方向 (如钢材/PCB/桥梁等已稳定开源数据集场景)"
    if risk == "high":
        return f"实验周期长达一年, {goal_level}路线只能做1轮实验, 毕业风险高. 建议收缩题目或换用公开数据集"
    if tier == "self_collect_data":
        return "需自采数据集, 建议先确认采集可行性 (设备/人力/时间), 或转向有公开数据集的相邻方向"
    if tier == "rent_compute":
        return "需租算力, 建议提前估算 GPU 成本, 或使用 Colab/学校集群降低开销"
    return "现有环境可做, 建议尽快启动 baseline 复现, 争取多做几轮消融实验"


def assess_reality(
    keywords: KeywordBreakdown,
    ev: EvidenceSummary,
    goal_level: str,
    raw_topic: str,
) -> RealityCheck:
    """执行现实约束评估."""
    tier, tier_reason = _determine_resource_tier(keywords, ev, raw_topic)
    cycle, cycle_reason = _determine_cycle(tier, ev)
    max_rounds, risk = get_cycle_matrix(goal_level, cycle)
    score = _calc_score(tier, cycle)
    suggestion = _gen_suggestion(tier, cycle, risk, goal_level)

    return RealityCheck(
        resource_tier=tier,
        resource_reason=tier_reason,
        experiment_cycle=cycle,
        cycle_reason=cycle_reason,
        max_experiment_rounds=max_rounds,
        graduation_risk=risk,
        score=score,
        suggestion=suggestion,
    )


# ---------- 融合降级 ---------- #

_VERDICT_ORDER = ["可做", "收缩后可做", "可转向", "暂缓", "不建议"]


def _downgrade_verdict(verdict: str, risk: GraduationRisk, tier: ResourceTier) -> str:
    """根据毕业风险降级 verdict."""
    if tier == "infeasible":
        return "不建议"

    if risk == "high":
        idx = _VERDICT_ORDER.index(verdict) if verdict in _VERDICT_ORDER else 1
        # 至少降一级
        idx = min(idx + 1, len(_VERDICT_ORDER) - 1)
        return _VERDICT_ORDER[idx]

    return verdict


def apply_reality_to_verdict(
    verdict: str,
    reality: RealityCheck,
) -> str:
    """将 RealityCheck 的毕业风险应用到可行性 verdict 上."""
    return _downgrade_verdict(verdict, reality.graduation_risk, reality.resource_tier)
