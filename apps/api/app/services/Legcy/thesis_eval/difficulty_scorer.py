"""Session 51: 项目难度与周期评估 (映射 RealityCheck 资源四层).

复用 S45 RealityCheck 资源四层, 加题录信号 (SOP §9):

| 难度 | RealityCheck 资源层 | 周期 | 典型 |
|------|---------------------|------|------|
| 低-中 | existing_env        | 0.5–2天/轮 | YOLO/U-Net 裂缝检测 |
| 中    | existing_env/rent   | 1–3天/轮  | 完整训练+消融 |
| 中-高 | self_collect_data   | 3–10天/轮 | 点云/SLAM/三维 |
| 高    | infeasible/hardware | 1–3周/轮  | 机械臂/医学/多模态攻防 |

判定信号 (按优先级):
1. 硬件平台 (机械臂/机器人/医学合规) → 高
2. 三维/点云/SLAM/多模态融合 → 中-高
3. SCADA/传统/能源实验台 → 中 (轻算力但数据/合规重)
4. YOLO/U-Net/普通检测 → 低-中 或 中
5. 缺陷+自采+标注重 → 提一档

核心约束:
- H100 不是默认需求; 真正风险是数据和硬件.
- 周期判断保守: 能跑通训练 ≠ 能完成论文级实验.
"""

from __future__ import annotations

import logging
from typing import Any

from ...schemas_thesis_eval import (
    Difficulty,
    ExperimentNeedTag,
    REALITY_TIER_BY_DIFFICULTY,
)

logger = logging.getLogger(__name__)

# 高难度信号词 (硬件/医学/复杂RL/多模态攻防)
_HIGH_SIGNALS = {
    "机械臂", "机器人", "抓取", "ros", "jetson", "伺服", "运动控制",
    "医学", "医疗", "患者", "ct", "mri", "超声", "人体",
    "强化学习", "rl", "对抗攻防", "多模态攻防",
}
# 中-高信号词 (三维/点云/SLAM/双目/时序)
_MID_HIGH_SIGNALS = {
    "点云", "slam", "三维", "3d", "rgb-d", "双目", "结构光",
    "多模态融合", "时序", "配准", "重建",
}
# 中信号词 (SCADA/能源/实验台/可靠性)
_MID_SIGNALS = {
    "scada", "故障诊断", "可靠性", "实验台", "叶片", "装备",
    "巡检", "电力", "轨交",
}
# 低-中信号词 (YOLO/U-Net/普通检测)
_LOW_MID_SIGNALS = {
    "yolo", "u-net", "unet", "缺陷检测", "目标检测", "图像分类",
    "裂缝", "废钢", "绝缘子", "违禁物",
}
# 升一档的加重词 (数据/标注重)
_ESCALATORS = {
    "缺陷", "小目标", "类别不均衡", "标注", "自采", "现场",
    "细粒度", "多类别",
}

# 难度 → 默认周期/repeatability (对齐测试集分布)
_DIFFICULTY_DEFAULTS: dict[Difficulty, tuple[str, str]] = {
    "低-中": ("0.5–3天/轮", "10–25轮"),
    "中": ("1–3天/轮", "8–15轮"),
    "中-高": ("3–10天/轮", "3–6轮"),
    "高": ("1–3周/轮", "1–3轮"),
}

# 难度 → RealityCheck 资源层 (复用 schemas_thesis_eval 映射)
# 高 → infeasible; 中-高 → self_collect_data; 中 → rent_compute; 低-中 → existing_env


def _text_lower(text: str) -> str:
    return (text or "").lower()


def _has_any(text_lower: str, words: set[str]) -> bool:
    return any(w in text_lower for w in words)


def determine_difficulty(
    title: str,
    abstract: str | None,
    needs: list[ExperimentNeedTag],
) -> Difficulty:
    """从题名+摘要+实验需求标签判定 4 档难度.

    优先级: 硬件/医学 (高) > 三维/SLAM (中-高) > SCADA/能源 (中) > YOLO/检测 (低-中/中).
    缺陷+自采+标注重 → 在基础档上提一档.
    """
    text = _text_lower(title) + " " + _text_lower(abstract or "")

    # --- 基础档 (按信号词优先级) ---
    if _has_any(text, _HIGH_SIGNALS) or "hardware_platform_required" in needs:
        base: Difficulty = "高"
    elif _has_any(text, _MID_HIGH_SIGNALS) or "large_gpu_optional" in needs:
        base = "中-高"
    elif _has_any(text, _MID_SIGNALS) or "cpu_or_light_gpu_ok" in needs:
        base = "中"
    elif _has_any(text, _LOW_MID_SIGNALS) or "single_gpu_ok" in needs:
        base = "低-中"
    else:
        base = "中"  # 默认中档 (保守)

    # --- 加重: 缺陷+自采+标注重 → 提一档 (但不超过 高) ---
    escalate = (
        ("self_collected_dataset" in needs and "annotation_heavy" in needs)
        or _has_any(text, _ESCALATORS)
    )
    if escalate:
        order: list[Difficulty] = ["低-中", "中", "中-高", "高"]
        idx = order.index(base)
        base = order[min(idx + 1, len(order) - 1)]

    # --- domain_data_permission_risk (医学/电力) → 至少 中-高 ---
    if "domain_data_permission_risk" in needs:
        order = ["低-中", "中", "中-高", "高"]
        idx = order.index(base)
        base = order[max(idx, 2)]  # 至少中-高

    return base


def score_difficulty(
    title: str,
    abstract: str | None,
    needs: list[ExperimentNeedTag],
) -> dict[str, Any]:
    """难度/周期/repeatability/feasibility/reality_tier 评估.

    Returns:
        {
            "difficulty": "中-高",
            "cycle": "3–10天/轮",
            "repeatability": "3–6轮",
            "graduation_feasibility": "收缩后可做",
            "reality_tier": "self_collect_data",
            "confidence": 0.6,
        }
    """
    difficulty = determine_difficulty(title, abstract, needs)
    cycle, repeatability = _DIFFICULTY_DEFAULTS[difficulty]
    reality_tier = REALITY_TIER_BY_DIFFICULTY[difficulty]
    feasibility = _difficulty_to_feasibility(difficulty, reality_tier, needs)
    confidence = _difficulty_confidence(difficulty, needs)

    return {
        "difficulty": difficulty,
        "cycle": cycle,
        "repeatability": repeatability,
        "graduation_feasibility": feasibility,
        "reality_tier": reality_tier,
        "confidence": confidence,
    }


def _difficulty_to_feasibility(
    difficulty: Difficulty,
    reality_tier: str,
    needs: list[ExperimentNeedTag],
) -> str:
    """难度 + 资源层 + 风险 → 5 档 graduation_feasibility.

    对齐 RealityCheck 的 5 档: 可做/收缩后可做/可转向/暂缓/不建议.
    """
    if difficulty == "低-中":
        return "可做"
    if difficulty == "中":
        # 有合规/权限风险 → 收缩后可做; 否则可做
        if "domain_data_permission_risk" in needs or "self_collected_dataset" in needs:
            return "收缩后可做"
        return "可做"
    if difficulty == "中-高":
        # 需砍范围
        if "hardware_platform_required" in needs:
            return "暂缓"
        return "收缩后可做"
    # 高
    if reality_tier == "infeasible" or "hardware_platform_required" in needs:
        return "不建议"
    return "暂缓"


def _difficulty_confidence(difficulty: Difficulty, needs: list[ExperimentNeedTag]) -> float:
    """启发式信心度: 信号越强越高."""
    base = {"低-中": 0.7, "中": 0.6, "中-高": 0.65, "高": 0.75}[difficulty]
    if needs:
        base = min(0.9, base + 0.05)
    return round(base, 2)
