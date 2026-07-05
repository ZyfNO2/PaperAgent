"""Feasibility assessor prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any

SYSTEM = "你是开题可行性评估员。根据证据数量区分：有baseline≥2+有repo→feasible(70-85)；有baseline≥1但无repo→risky(40-60)；无baseline→not_recommended(10-30)。不得对所有case给同一个score。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline数: {n_baseline}, Parallel数: {n_parallel}, Dataset数: {n_dataset}, Repo数: {n_repo}

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=50字","100_plus_formula":{{"baseline_weight":0,"module_weights":[],"estimated_total":0}},"degradation_paths":[]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, n_baseline: int, n_parallel: int, n_dataset: int, n_repo: int) -> dict[str, str]:
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], n_baseline=n_baseline, n_parallel=n_parallel,
        n_dataset=n_dataset, n_repo=n_repo)}
