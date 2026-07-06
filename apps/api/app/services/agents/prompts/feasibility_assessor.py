"""Feasibility assessor prompt — Re2.1 deep fix.

Passes paper titles + repo status so LLM can differentiate
"2 baseline with repo" vs "2 baseline without repo".
"""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = ("你是开题可行性评估员。根据证据数量和内容判断能不能保毕业。"
          "不得对所有case给同一个score。只输出JSON。")

USER_TEMPLATE = """题目: {topic}

Baseline论文({n_baseline}篇):
{baseline_summary}

Parallel论文({n_parallel}篇):
{parallel_summary}

数据集: {n_dataset}个, 代码仓库: {n_repo}个

评估标准:
- feasible (60-100分): baseline>=1 + 有数据集或repo，或有充足的parallel论文可参考
- risky (35-59分): baseline>=1 但数据集/repo不足
- not_recommended (0-34分): 无baseline或题目过于宽泛

注意: 根据 baseline 论文的具体内容、repo 有无、数据集匹配度给不同的 score。
同样数量的 baseline，有 repo 的比没 repo 的 score 高 10-20 分。

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=100字，引用具体论文","100_plus_formula":{{"baseline_weight":0,"module_weights":[],"estimated_total":0,"assessment":"足够毕业|勉强|不足"}},"degradation_paths":["具体退化路线"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]], parallels: list[dict[str, Any]],
          n_dataset: int, n_repo: int) -> dict[str, str]:
    # Pass paper titles + repo status for LLM to differentiate
    baseline_summary = "\n".join(
        f"- {p.get('title', '')[:80]} (repo: {'有' if p.get('official_code_url') or p.get('url') else '无'})"
        for p in baselines[:5]
    ) or "无 baseline 论文"

    parallel_summary = "\n".join(
        f"- {p.get('title', '')[:80]}"
        for p in parallels[:5]
    ) or "无 parallel 论文"

    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        n_baseline=len(baselines),
        baseline_summary=baseline_summary,
        n_parallel=len(parallels),
        parallel_summary=parallel_summary,
        n_dataset=n_dataset, n_repo=n_repo)}
