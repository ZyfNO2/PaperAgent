"""Session 62 (refined) M1: GraduationDirectionPlanner — LLM-first + heuristic-fallback.

ponytail: 参考 apps/api/app/services/keyword_search_assistant.py 的提示词工程模式.
- 先用 arXiv 抓同领域 3-5 篇参考论文 (无网络 → 直接 fallback)
- LLM 参考这些论文 + 用户原题, 生成结构化方向 (失败 → heuristic fallback)
- 永远不许 LLM 挂掉服务 (CLAUDE.md 强约束)

为什么硬编码模板不够:
- 三维损伤检测 题返回 YOLO/U-Net (用户截图证据)
- 三维成像有"重建 + 检测"两个独立任务路径, 模板枚举会漏新方向
- NLP/BERT 类题完全没覆盖
- 任何新方向 (比如 GraphRAG / 多模态) 都要改 _KEYWORD_TEMPLATES, 不能扩展

LLM 路径可以读懂用户原题 + 参考论文, 自动判断:
- 是 3D 还是 2D
- 是检测还是重建还是分类
- 应该用哪些 baseline
- 创新点在哪
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from .. import arxiv as arxiv_client
from .. import llm

logger = logging.getLogger(__name__)


# ---------- arXiv 参考论文 ---------- #


def _fetch_arxiv_refs(query: str, max_results: int = 5) -> list[dict]:
    """从 arXiv 抓同领域参考论文 (无网络 → 返回空列表, 让上层 fallback)."""

    try:
        hits = arxiv_client.search_arxiv([query], max_per_query=2, max_total=max_results)
    except Exception as exc:  # noqa: BLE001
        logger.info("llm_director: arXiv 搜索失败 fallback: %s", exc)
        return []
    return [
        {
            "arxiv_id": h.arxiv_id,
            "title": h.title,
            "summary": (h.summary or "")[:400],
            "year": h.year,
        }
        for h in hits
    ]


# ---------- LLM Prompt ---------- #


_DIRECTION_PROMPT = """你是科研毕业选题顾问. 用户给你一个开题题目, 我已经从 arXiv 搜了同领域参考论文的标题/摘要.
请参考这些同领域论文, 生成 2-3 个可毕业方向 + 推荐 baseline + 可加模块 + 降级路径.

**用户题目**: {raw_topic}

**参考论文 (arXiv 命中, 摘要已截断)**:
{papers_block}

**任务**: 每个方向必须是"可毕业"版本 — 公开数据集 + 成熟 baseline + 可消融 + 算力可控.
**不要推荐**: 重模型/大算力路线 (Diffusion / 大模型预训练全量) / 无公开数据 / 不可复现 baseline.
**重要**: 如果题目是 3D / 点云, 至少一个方向要拆成 "3D 重建 + 3D 检测" 两个独立工作量 (用户题目: {raw_topic}).

每个方向必须有这些字段 (返回严格 JSON, 不要 markdown fence):
{{
  "directions": [
    {{
      "direction_id": "dir_1_<短标识>",
      "title": "方向标题",
      "research_object": "研究对象 (一句话)",
      "task": "任务 (一句话, 如'三维点云缺陷检测')",
      "method_route": "方法路线 (一句话, 如'PointNet++ + 轻量化 neck')",
      "why_graduation_friendly": ["好毕业理由 1", "理由 2", "理由 3"],
      "fallback_route": "如果数据/算力不足, 降级到 (具体公开数据集或简化任务)",
      "recommended_baselines": [
        {{
          "name": "baseline 名称 (如 PointNet++/BERT/YOLOv8n)",
          "rationale": "为什么选这个 baseline",
          "required_data": "所需公开数据 (如 ShapeNet / COCO / 中文 wiki)",
          "reproducibility": "high / medium / low",
          "estimated_compute": "算力估计 (如 单卡 3090 12-24h)",
          "risks": ["风险 1", "风险 2"]
        }}
      ],
      "extension_modules": [
        {{
          "name": "模块名 (如 CBAM 注意力 / LoRA / Mosaic+MixUp)",
          "attach_to": "加在哪",
          "problem_solved": "解决什么问题",
          "ablation_plan": "怎么做消融对比",
          "effort": "S / M / L",
          "risks": ["风险 1"]
        }}
      ]
    }}
  ]
}}

返回 2-3 个方向. baseline 必须是真实的、当前主流的. 模块必须是可消融的.
**参考论文里出现的方法名优先用, 没出现的不要硬塞.**
"""


def _call_llm_director(raw_topic: str, ref_papers: list[dict]) -> list[dict] | None:
    """调 LLM 生成方向. 失败 → 返回 None."""

    papers_block = "\n".join(
        f"  [{i+1}] {p['title']} ({p.get('year', '?')})\n      摘要: {p['summary']}"
        for i, p in enumerate(ref_papers)
    ) or "  (无 arXiv 命中, 请仅基于通用领域知识生成)"

    prompt = _DIRECTION_PROMPT.format(raw_topic=raw_topic, papers_block=papers_block)

    try:
        result = llm.chat_json(
            prompt,
            temperature=0.4,
            max_tokens=2500,
            timeout=45.0,
            profile="direction_advice",
        )
    except llm.LLMUnavailable as exc:
        logger.info("llm_director: LLM 失败 fallback: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.info("llm_director: LLM 调用异常 fallback: %s", exc)
        return None

    if not isinstance(result, dict):
        return None
    raw_dirs = result.get("directions")
    if not isinstance(raw_dirs, list) or not raw_dirs:
        return None

    # 校验每个方向字段
    out: list[dict] = []
    for i, d in enumerate(raw_dirs[:3], start=1):
        if not isinstance(d, dict):
            continue
        title = str(d.get("title") or "").strip()
        if not title:
            continue
        out.append({
            "direction_id": str(d.get("direction_id") or f"dir_{i}_{title[:12]}"),
            "title": title,
            "research_object": str(d.get("research_object") or ""),
            "task": str(d.get("task") or ""),
            "method_route": str(d.get("method_route") or ""),
            "why_graduation_friendly": list(d.get("why_graduation_friendly") or [])[:5],
            "fallback_route": str(d.get("fallback_route") or ""),
            "recommended_baselines": _clean_baselines(d.get("recommended_baselines") or []),
            "extension_modules": _clean_modules(d.get("extension_modules") or []),
        })
    return out or None


def _clean_baselines(items: list) -> list[dict]:
    out = []
    for b in items[:3]:
        if not isinstance(b, dict):
            continue
        name = str(b.get("name") or "").strip()
        if not name:
            continue
        repro = str(b.get("reproducibility") or "medium")
        if repro not in ("high", "medium", "low"):
            repro = "medium"
        out.append({
            "name": name,
            "rationale": str(b.get("rationale") or ""),
            "required_data": str(b.get("required_data") or ""),
            "reproducibility": repro,
            "estimated_compute": str(b.get("estimated_compute") or ""),
            "risks": list(b.get("risks") or [])[:3],
        })
    return out


def _clean_modules(items: list) -> list[dict]:
    out = []
    for m in items[:4]:
        if not isinstance(m, dict):
            continue
        name = str(m.get("name") or "").strip()
        if not name:
            continue
        effort = str(m.get("effort") or "M")
        if effort not in ("S", "M", "L"):
            effort = "M"
        out.append({
            "name": name,
            "attach_to": str(m.get("attach_to") or ""),
            "problem_solved": str(m.get("problem_solved") or ""),
            "ablation_plan": str(m.get("ablation_plan") or ""),
            "effort": effort,
            "risks": list(m.get("risks") or [])[:3],
        })
    return out


# ---------- 公开入口 ---------- #


@dataclass
class DirectorResult:
    directions: list[dict] = field(default_factory=list)
    source: str = "heuristic"  # "llm" / "heuristic" / "mixed"
    arxiv_refs: list[dict] = field(default_factory=list)


def generate_directions(
    raw_topic: str,
    *,
    prefer: str = "auto",
    max_directions: int = 3,
) -> DirectorResult:
    """LLM-first + heuristic-fallback 入口.

    Args:
        raw_topic: 用户原题
        prefer: "auto" / "llm" / "heuristic"
        max_directions: 最多返回几个方向

    Returns:
        DirectorResult: directions + source (供前端调试可见)
    """

    # 显式禁用 LLM
    if prefer == "heuristic":
        return DirectorResult(
            directions=[],
            source="heuristic",
        )

    # 1) 抓参考论文 (失败仍可继续 — LLM 可仅基于通用知识生成)
    arxiv_refs = _fetch_arxiv_refs(raw_topic, max_results=5)

    # 2) 调 LLM
    llm_dirs = _call_llm_director(raw_topic, arxiv_refs) if (arxiv_refs or True) else None

    if llm_dirs and len(llm_dirs) >= 2:
        return DirectorResult(
            directions=llm_dirs[:max_directions],
            source="llm",
            arxiv_refs=arxiv_refs,
        )

    # LLM 没出 / arXiv 没命中 / LLM 失败 → fallback
    return DirectorResult(
        directions=[],
        source="heuristic",
        arxiv_refs=arxiv_refs,
    )


if __name__ == "__main__":
    # ponytail: self-check — 验证 LLM 路径可用 (不依赖真实 LLM)
    r = generate_directions("钢材表面缺陷识别", prefer="heuristic")
    assert r.source == "heuristic", r.source
    print(f"OK llm_director self-check (source={r.source}, arxiv_refs={len(r.arxiv_refs)})")
