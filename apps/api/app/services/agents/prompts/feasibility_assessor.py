"""Feasibility assessor prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是开题可行性评估员。基于论文证据判断能不能保毕业。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文({n_baseline}篇):
{baselines_json}

Parallel论文({n_parallel}篇):
{parallels_json}

数据集: {n_dataset}个, 代码仓库: {n_repo}个

评估标准:
- feasible (70-100分): baseline>=2 + 有数据集 + 有repo
- risky (40-69分): baseline>=1 但数据集/repo不足
- not_recommended (0-39分): 无baseline或题目过于宽泛

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=100字，引用具体论文","100_plus_formula":{{"baseline_weight":0,"module_weights":[],"estimated_total":0,"assessment":"足够毕业|勉强|不足"}},"degradation_paths":["具体退化路线"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]], parallels: list[dict[str, Any]],
          n_dataset: int, n_repo: int) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""),
                 "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", ""),
                 "venue": i.get("venue", i.get("source", ""))}
                for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        n_baseline=len(baselines),
        baselines_json=_json.dumps(slim(baselines), ensure_ascii=False),
        n_parallel=len(parallels),
        parallels_json=_json.dumps(slim(parallels), ensure_ascii=False),
        n_dataset=n_dataset, n_repo=n_repo)}
