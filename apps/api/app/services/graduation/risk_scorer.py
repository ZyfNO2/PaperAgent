"""Session 62 M2: GraduationRiskScorer — heuristic 7-dim scoring.

ponytail: 不调 LLM, 不重写 scoring service; 用 dict + 简单加权。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .direction_planner import GraduationDirection

RiskLevel = Literal["low", "medium", "high"]


@dataclass
class RiskBreakdown:
    score: float
    risk_level: RiskLevel
    items: list[dict] = field(default_factory=list)


# 7 维评分: 满分 100, 各维权重和为 1.0
_WEIGHTS: dict[str, float] = {
    "dataset_availability": 0.25,
    "baseline_reproducibility": 0.20,
    "compute_cost": 0.10,
    "innovation_simplicity": 0.10,
    "experiment_rounds": 0.10,
    "writing_explainability": 0.15,
    "fallback_path": 0.10,
}


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _infer_dimension_scores(
    direction: GraduationDirection,
    has_paper: bool,
    has_dataset: bool,
    has_repo: bool,
    has_local_rag: bool,
) -> dict[str, tuple[float, str]]:
    """对 7 维各打分 0-100 + 备注."""

    method_route = (direction.method_route or "").lower()
    fallback = bool(direction.fallback_route)
    title = direction.title or ""

    # 大算力 / 重模型关键词
    heavy_keywords = ("大模型", "llm", "transformer", "diffusion", "扩散", "预训练", "3d 大型")
    heavy = any(kw in method_route or kw in title for kw in heavy_keywords)

    # 数据集 / baseline 维度
    dataset_score = 85.0 if has_dataset else 35.0
    if has_dataset:
        dataset_note = "有公开数据集候选"
    else:
        dataset_note = "无公开数据集候选, 需要降级方向"

    baseline_score = 85.0 if has_repo else 40.0
    if has_repo:
        baseline_note = "有可复现工程候选"
    else:
        baseline_note = "无工程候选, 需自实现 baseline"

    # 算力: 重模型扣分
    if heavy:
        compute_score = 35.0
        compute_note = "方法路径涉及大算力模型, 风险较高"
    else:
        compute_score = 80.0
        compute_note = "轻量级方法, 单卡可跑"

    # 创新简单: 维度越窄, 越可做小创新
    innovation_score = 75.0
    if "轻量化" in title or "轻量" in method_route:
        innovation_note = "已锁定轻量化方向, 创新空间明确"
    else:
        innovation_note = "创新空间待用户进一步选择"

    # 实验轮次: 论文/工程越多, 越有 baseline 可对比
    if has_paper and has_repo:
        experiment_score = 80.0
        experiment_note = "有论文 + 工程, 可做多轮对比"
    elif has_paper or has_repo:
        experiment_score = 65.0
        experiment_note = "有论文或工程, 实验可设计"
    else:
        experiment_score = 40.0
        experiment_note = "无 baseline 候选, 实验设计难度高"

    # 写作解释: 有 fallback / RAG 引用加分
    if fallback and has_local_rag:
        writing_score = 85.0
        writing_note = "有降级路径 + 本地文献片段支撑"
    elif fallback:
        writing_score = 70.0
        writing_note = "有降级路径"
    else:
        writing_score = 55.0
        writing_note = "缺降级路径, 答辩解释成本较高"

    # fallback: 直接打分
    fallback_score = 90.0 if fallback else 30.0
    fallback_note = "已给出降级路径" if fallback else "未给出降级路径, 风险偏高"

    return {
        "dataset_availability": (dataset_score, dataset_note),
        "baseline_reproducibility": (baseline_score, baseline_note),
        "compute_cost": (compute_score, compute_note),
        "innovation_simplicity": (innovation_score, innovation_note),
        "experiment_rounds": (experiment_score, experiment_note),
        "writing_explainability": (writing_score, writing_note),
        "fallback_path": (fallback_score, fallback_note),
    }


def _to_risk_level(total: float) -> RiskLevel:
    if total >= 70:
        return "low"
    if total >= 50:
        return "medium"
    return "high"


def score_direction(
    direction: GraduationDirection,
    *,
    has_paper: bool = False,
    has_dataset: bool = False,
    has_repo: bool = False,
    has_local_rag: bool = False,
) -> RiskBreakdown:
    """计算单方向毕业友好评分 (0-100)."""

    dims = _infer_dimension_scores(direction, has_paper, has_dataset, has_repo, has_local_rag)
    items: list[dict] = []
    total = 0.0
    for key, weight in _WEIGHTS.items():
        s, note = dims[key]
        items.append({"key": key, "label": key, "score": round(s, 1), "weight": weight, "note": note})
        total += s * weight
    total = round(_clamp(total), 1)

    # 数据集缺失 + 无降级 → 强制降档
    if not has_dataset and not direction.fallback_route:
        total = min(total, 40.0)

    return RiskBreakdown(score=total, risk_level=_to_risk_level(total), items=items)


if __name__ == "__main__":
    # ponytail: self-check
    d = GraduationDirection(
        direction_id="dir_1_test",
        title="基于公开裂缝数据集的轻量化检测",
        research_object="裂缝",
        task="目标检测",
        method_route="YOLOv8n",
        why_graduation_friendly=["公开数据丰富"],
        fallback_route="降级到 crack500",
    )
    r1 = score_direction(d, has_paper=True, has_dataset=True, has_repo=True, has_local_rag=True)
    r2 = score_direction(d, has_paper=False, has_dataset=False, has_repo=False, has_local_rag=False)
    assert r1.score > r2.score, (r1.score, r2.score)
    assert r1.risk_level in ("low", "medium", "high"), r1.risk_level
    assert len(r1.items) == 7, len(r1.items)
    print(f"OK risk_scorer self-check (with_evidence={r1.score}, without={r2.score})")