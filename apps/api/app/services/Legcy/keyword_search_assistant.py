"""LLM 驱动的关键词搜索助手 (Session 6 §13.1).

目标: 调 arXiv/Semantic Scholar 搜同领域 3-5 篇高引论文, 抽取作者关键词,
让 LLM **参考**这些关键词生成最终 keywords (而不是凭空写).

Fallback: 任何环节 (网络 / 解析 / LLM 失败) → 返回 None, 让上层继续用现有路径.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from . import arxiv as arxiv_client
from . import llm

logger = logging.getLogger(__name__)


# ---------- 工具 ---------- #


def _extract_arxiv_keywords(papers: list[dict[str, Any]]) -> list[str]:
    """从 arXiv 命中论文标题/摘要里抽 token 作为参考关键词 (粗启发式).

    不用 LLM, 走正则, fallback 路径.
    """

    if not papers:
        return []
    tokens: set[str] = set()
    for p in papers[:5]:
        title = p.get("title", "")
        summary = p.get("summary", "")
        for text in (title, summary):
            # 拆中文 2-6 字词 + 英文 3+ 字母
            tokens.update(re.findall(r"[一-龥]{2,6}", text))
            tokens.update(re.findall(r"[A-Za-z]{3,}", text.lower()))
    # 过滤掉常见停用词
    stop = {
        "the", "and", "for", "with", "this", "from", "that", "are", "was",
        "have", "has", "been", "will", "their", "which", "paper", "study",
        "research", "based", "using", "approach", "method", "results",
        "我们", "研究", "提出", "方法", "基于", "通过", "分析", "模型",
        "实验", "数据", "结果", "本文", "针对", "设计", "实现", "系统",
        "问题", "场景", "情况", "需要", "可以", "一种", "对", "在",
    }
    return sorted(t for t in tokens if t not in stop and len(t) >= 2)[:30]


def _arxiv_search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """调 arXiv 搜同领域 3-5 篇, 返回 dict 列表 (title/summary/year/arxiv_id)."""

    try:
        hits = arxiv_client.search_arxiv([query], max_per_query=2, max_total=max_results)
    except Exception as exc:  # noqa: BLE001
        logger.info("arXiv 搜索失败: %s", exc)
        return []
    return [
        {
            "arxiv_id": h.arxiv_id,
            "title": h.title,
            "summary": h.summary or "",
            "year": h.year,
        }
        for h in hits
    ]


# ---------- 主函数 ---------- #


_KEYWORD_PROMPT = """你是科研选题助手. 用户给你一个**开题题目**, 我已经从 arXiv 搜了同领域 3-5 篇高引论文的标题/摘要.
请参考这些同领域论文, 给用户题目生成结构化关键词.

**用户题目**: {raw_topic}

**参考论文 (arXiv 命中)**:
{papers_block}

**输出要求**: 严格 JSON, 不要 markdown fence, 不要任何解释. 字段:
{{
  "method_keywords": ["方法词 1", "方法词 2", ...],     // 3-5 个, 用 arXiv 论文里出现的高频方法词
  "task_keywords": ["任务词 1", "任务词 2", ...],       // 3-5 个, 同领域在做的任务
  "object_keywords": ["对象词 1", "对象词 2", ...],     // 3-5 个, 同领域研究对象
  "scenario_keywords": ["场景词 1", "场景词 2", ...],   // 0-3 个
  "metric_keywords": ["指标词 1", "指标词 2", ...],     // 0-3 个, 同领域常用评价指标
  "risk_terms": ["风险词 1", ...],                       // 0-3 个, 题目里夸大/空泛的词
  "rationale": "一句话说明为什么这些关键词适合这个题目"
}}

参考论文里没出现的词**不要硬塞**, 凭空的词会让评分失效. 优先复用参考论文 + 题目本身的高频词.
"""


def search_assistant(raw_topic: str, prefer: str = "auto") -> dict[str, Any] | None:
    """Session 6 §13.1: LLM 搜索助手.

    Returns:
        dict 形如 {"method_keywords": [...], "task_keywords": [...], ...} 或 None (失败).
    """

    if prefer == "heuristic":
        return None

    # 1) arXiv 搜同领域 (query 直接用用户原题)
    ref_papers = _arxiv_search(raw_topic, max_results=5)
    if not ref_papers:
        logger.info("搜索助手: arXiv 无命中, fallback")
        return None

    # 2) 构造 prompt
    papers_block = "\n".join(
        f"  [{i+1}] {p['title']} ({p.get('year', '?')})\n      摘要: {(p['summary'] or '')[:300]}"
        for i, p in enumerate(ref_papers[:5])
    )
    prompt = _KEYWORD_PROMPT.format(raw_topic=raw_topic, papers_block=papers_block)

    # 3) 调 LLM
    try:
        result = llm.chat_json(prompt, temperature=0.3, max_tokens=1500, timeout=30.0)
    except llm.LLMUnavailable as exc:
        logger.info("搜索助手: LLM 失败 fallback: %s", exc)
        return None

    # 4) 校验
    if not isinstance(result, dict):
        return None
    out = {
        "method_keywords": list(result.get("method_keywords") or [])[:5],
        "task_keywords": list(result.get("task_keywords") or [])[:5],
        "object_keywords": list(result.get("object_keywords") or [])[:5],
        "scenario_keywords": list(result.get("scenario_keywords") or [])[:3],
        "metric_keywords": list(result.get("metric_keywords") or [])[:3],
        "risk_terms": list(result.get("risk_terms") or [])[:3],
        "rationale": str(result.get("rationale") or ""),
        "ref_paper_count": len(ref_papers),
    }
    if not out["method_keywords"] and not out["task_keywords"] and not out["object_keywords"]:
        return None
    return out


def merge_with_heuristic(
    assistant_kw: dict[str, Any],
    heuristic_kw: dict[str, list[str]],
) -> dict[str, list[str]]:
    """合并 LLM 搜索助手输出 + 启发式输出 (启发式兜底).

    策略: LLM 搜索助手的优先, 启发式补全缺失字段. 去重保序.
    """

    out: dict[str, list[str]] = {}
    for field in ("method_keywords", "task_keywords", "object_keywords",
                  "scenario_keywords", "metric_keywords", "risk_terms"):
        llm_list = assistant_kw.get(field) or []
        heu_list = heuristic_kw.get(field) or []
        merged: list[str] = []
        for k in list(llm_list) + list(heu_list):
            if k and k not in merged:
                merged.append(k)
            if len(merged) >= 6:
                break
        out[field] = merged
    return out
