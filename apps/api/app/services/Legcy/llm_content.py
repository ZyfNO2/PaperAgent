"""LLM 驱动的内容生成 (Session 6 §3-§4).

- recommend_proposal_llm: 写推荐题目 + 工作包 + 推荐理由
- light_review_llm: 写 5 维审核 comment
"""

from __future__ import annotations

import logging
from typing import Any

from . import llm

logger = logging.getLogger(__name__)


# ---------- §3 LLM recommend_proposal ---------- #


_RECOMMEND_PROMPT = """你是中国研究生开题选题推荐助手. 给定一个**原题** + **关键词** + **证据摘要** + **可行性判断**,
输出结构化推荐 (推荐题目 + 推荐理由 + 2 个工作包), 严格 JSON, 无 markdown fence.

**原题**: {raw_topic}
**目标档位**: {goal_level}

**关键词**:
  method: {method_kw}
  task: {task_kw}
  object: {object_kw}
  scenario: {scenario_kw}
  metric: {metric_kw}
  risk: {risk_kw}

**证据摘要**:
  arxiv 命中: {arxiv_count} 篇, 总 {paper_count} 篇
  数据集: {dataset_names} (有公开数据集: {has_dataset})
  baseline: {baseline_names} (有可复现 baseline: {has_baseline})
  评价指标: {metrics}

**可行性判断**: verdict={verdict}, 原因: {feas_reason}

**输出 JSON 格式** (严格):
{{
  "recommended_topic": "推荐的开题题目 (基于原题, 反映 evidence 现状, 不要硬编码钢材等具象对象, 沿用原题对象)",
  "recommendation_reasons": [
    "理由 1 (基于 arxiv 命中, e.g. N 篇真实论文方向成熟)",
    "理由 2 (基于 baseline/dataset)",
    "理由 3 (基于 metric/scenario)",
    "理由 4 (基于原题 risk_terms 收缩)"
  ],
  "work_packages": [
    {{
      "wp_id": "WP1",
      "title": "工作包 1 标题 (基于 evidence, 不要通用模板)",
      "research_question": "研究问题",
      "method_approach": "方法思路",
      "data_source": "数据来源 (用 evidence 里的真实数据集名, 或自采)",
      "experiment_plan": "实验计划 (报告什么指标)",
      "chapter": "第三章"
    }},
    {{
      "wp_id": "WP2",
      "title": "工作包 2 标题 (在 WP1 基础上做改进/消融)",
      "research_question": "...",
      "method_approach": "...",
      "data_source": "同 WP1",
      "experiment_plan": "消融/对比实验",
      "chapter": "第四章"
    }}
  ]
}}

要求:
1. recommended_topic 反映原题语义, 不要把 "PINN" 改成 "YOLO" (基于原题)
2. work_packages 基于 evidence 真实情况, 不要硬编码 NEU-DET / DeepPCB 等
3. 数据来源: 真实有公开数据集 → 用; 没有 → 写"自采 100-200 张"
4. reasons 写 3-4 条, 每条 < 30 字
"""


def recommend_proposal_llm(
    raw_topic: str,
    goal_level: str,
    keywords: dict[str, list[str]],
    arxiv_count: int,
    paper_count: int,
    dataset_names: list[str],
    has_dataset: bool,
    baseline_names: list[str],
    has_baseline: bool,
    metrics: list[str],
    verdict: str,
    feas_reason: str,
) -> dict[str, Any] | None:
    """LLM 写推荐题目 + WP + reasons. 失败返回 None."""

    prompt = _RECOMMEND_PROMPT.format(
        raw_topic=raw_topic,
        goal_level=goal_level,
        method_kw=", ".join(keywords.get("method_keywords") or []),
        task_kw=", ".join(keywords.get("task_keywords") or []),
        object_kw=", ".join(keywords.get("object_keywords") or []),
        scenario_kw=", ".join(keywords.get("scenario_keywords") or []),
        metric_kw=", ".join(keywords.get("metric_keywords") or []),
        risk_kw=", ".join(keywords.get("risk_terms") or []),
        arxiv_count=arxiv_count,
        paper_count=paper_count,
        dataset_names=", ".join(dataset_names) or "(无)",
        has_dataset=has_dataset,
        baseline_names=", ".join(baseline_names) or "(无)",
        has_baseline=has_baseline,
        metrics=", ".join(metrics) or "(无)",
        verdict=verdict,
        feas_reason=feas_reason,
    )
    try:
        result = llm.chat_json(
            prompt,
            temperature=0.4,
            max_tokens=2000,
            timeout=30.0,
            profile="direction_advice",
        )
    except llm.LLMUnavailable as exc:
        logger.info("LLM recommend 失败: %s", exc)
        return None
    if not isinstance(result, dict):
        return None
    if not result.get("recommended_topic") or not result.get("work_packages"):
        return None
    return result


# ---------- §4 LLM light_review ---------- #


_REVIEW_PROMPT = """你是中国研究生开题模拟审核员. 给定**原题** + **证据摘要** + **可行性判断**, 对 5 个维度各打分 + 写 comment.

**原题**: {raw_topic}
**目标档位**: {goal_level}

**证据摘要**:
  arxiv: {arxiv_count} 篇 (总 {paper_count})
  数据集: {dataset_names} (有公开: {has_dataset})
  baseline: {baseline_names} (有可复现: {has_baseline})
  指标: {metrics}

**可行性**: verdict={verdict}, 原因: {feas_reason}

**5 维审核** (每维给 result: "通过" / "有条件通过" / "需补充" / "不通过", 加 comment 50 字以内):

1. 题目边界: 研究对象/任务是否具体? 是否有"硬指标"可量化?
2. 数据集: 是否有公开数据集? 自采可行性?
3. Baseline: 是否有可复现 baseline? 复现成本?
4. 工作量: 工作包数 / 风险词 / 时间投入评估
5. 开题表达: 方法词 + 评价指标 + 场景词是否齐?

**严格输出 JSON** (无 markdown fence, 无解释):
{{
  "verdict": "通过 / 有条件通过 / 需修改 / 不建议",
  "summary": "一句话总结 (30 字内)",
  "checks": [
    {{"dimension": "题目边界", "result": "通过|有条件通过|需补充|不通过", "comment": "..."}},
    {{"dimension": "数据集", "result": "...", "comment": "..."}},
    {{"dimension": "Baseline", "result": "...", "comment": "..."}},
    {{"dimension": "工作量", "result": "...", "comment": "..."}},
    {{"dimension": "开题表达", "result": "...", "comment": "..."}}
  ],
  "revision_checklist": ["[题目边界] ...", "[数据集] ...", ...]
}}
"""


def light_review_llm(
    raw_topic: str,
    goal_level: str,
    arxiv_count: int,
    paper_count: int,
    dataset_names: list[str],
    has_dataset: bool,
    baseline_names: list[str],
    has_baseline: bool,
    metrics: list[str],
    verdict: str,
    feas_reason: str,
) -> dict[str, Any] | None:
    """LLM 写 5 维审核. 失败返回 None."""

    prompt = _REVIEW_PROMPT.format(
        raw_topic=raw_topic,
        goal_level=goal_level,
        arxiv_count=arxiv_count,
        paper_count=paper_count,
        dataset_names=", ".join(dataset_names) or "(无)",
        has_dataset=has_dataset,
        baseline_names=", ".join(baseline_names) or "(无)",
        has_baseline=has_baseline,
        metrics=", ".join(metrics) or "(无)",
        verdict=verdict,
        feas_reason=feas_reason,
    )
    try:
        result = llm.chat_json(
            prompt,
            temperature=0.3,
            max_tokens=2000,
            timeout=30.0,
            profile="light_review",
        )
    except llm.LLMUnavailable as exc:
        logger.info("LLM light_review 失败: %s", exc)
        return None
    if not isinstance(result, dict):
        return None
    if not result.get("verdict") or not result.get("checks"):
        return None
    return result
