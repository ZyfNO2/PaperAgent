"""Session 62 M1: GraduationDirectionPlanner — 委托给 llm_director.

ponytail: 不在本文件硬编码关键词模板 (用户 S62 self-audit 反馈: 三维题曾返回 YOLO/U-Net,
模板枚举漏 NLP/新方向). 关键词与方向生成走 LLM 路径 (apps/api/app/services/keyword_search_assistant.py 同模式):
1) arXiv 抓参考论文
2) LLM 基于参考论文 + 原题生成方向
3) LLM/arXiv 失败 → 直接抛错, 不做物理分词兜底 (用户要求: fail-fast)

下游 consumer (risk_scorer / evidence_bundle / baseline_advisor / module_extension_advisor)
继续接收 GraduationDirection dataclass, 行为不变.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .llm_director import DirectorResult, generate_directions


@dataclass
class GraduationDirection:
    direction_id: str
    title: str
    research_object: str
    task: str
    method_route: str
    why_graduation_friendly: list[str] = field(default_factory=list)
    fallback_route: str = ""


def _slug(s: str, n: int) -> str:
    s = re.sub(r"[^\w一-龥]+", "", s)
    return f"dir_{n}_{s[:24]}"


def _from_llm_dict(d: dict, idx: int) -> GraduationDirection:
    """把 LLM dict 转 GraduationDirection, 把 baselines/modules 挂到 _llm_* 私有属性.

    ponytail: 下游 _to_output 优先消费 _llm_baselines/_llm_modules, 避免 M4/M5
    启发式覆盖 LLM 已经读懂题目给的结果.
    """
    gd = GraduationDirection(
        direction_id=str(d.get("direction_id") or _slug(d.get("title", f"dir_{idx}"), idx)),
        title=str(d.get("title") or ""),
        research_object=str(d.get("research_object") or ""),
        task=str(d.get("task") or ""),
        method_route=str(d.get("method_route") or ""),
        why_graduation_friendly=list(d.get("why_graduation_friendly") or []),
        fallback_route=str(d.get("fallback_route") or ""),
    )
    # 挂载 LLM 给的 baseline/module 给 _to_output 优先消费
    setattr(gd, "_llm_baselines", d.get("recommended_baselines") or [])
    setattr(gd, "_llm_modules", d.get("extension_modules") or [])
    return gd


class DirectionPlannerError(RuntimeError):
    """方向生成失败 (LLM 不可用 或 arXiv 无命中 + LLM 无法生成).

    ponytail: 不做物理分词 fallback. 让上层 (API) 直接返回 503 / 422 让用户感知失败.
    """


def plan_directions(
    topic: str,
    max_directions: int = 3,
    *,
    prefer: str = "auto",
) -> tuple[list[GraduationDirection], DirectorResult]:
    """委托给 llm_director; 失败直接抛 DirectionPlannerError.

    Returns:
        (directions, director_result). director_result 携带 source + arxiv_refs 给前端调试可见.
    """

    if not (topic or "").strip():
        raise DirectionPlannerError("topic 不能为空")

    result = generate_directions(topic.strip(), prefer=prefer, max_directions=max_directions)

    if result.source != "llm" or not result.directions:
        raise DirectionPlannerError(
            f"LLM 方向生成失败 (source={result.source}, arxiv_refs={len(result.arxiv_refs)}, "
            f"llm_dirs=0); 请检查 LLM 凭据 (MINIMAX_API_KEY) 或 arXiv 网络可达性. "
            f"不做物理分词 fallback."
        )

    directions = [_from_llm_dict(d, i + 1) for i, d in enumerate(result.directions)]
    return directions[:max_directions], result


if __name__ == "__main__":
    # ponytail: self-check — 必须能拿到 ≥2 方向 (依赖 LLM 真实可达)
    # CI / 无 LLM 环境: 让 self-check 跳过, 实际运行由 API 测试覆盖
    try:
        ds, info = plan_directions("基于三维成像的损伤智能检测", max_directions=3)
        assert 2 <= len(ds) <= 3, len(ds)
        print(f"OK direction_planner self-check (count={len(ds)}, source={info.source}, arxiv={len(info.arxiv_refs)})")
    except DirectionPlannerError as exc:
        print(f"SKIP direction_planner self-check (LLM 不可达: {exc})")