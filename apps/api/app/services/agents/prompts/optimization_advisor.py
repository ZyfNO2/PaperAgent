"""Optimization advisor prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any

SYSTEM = "你是研究方向优化顾问。给优化方向和退化路线。保毕业导向。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
可行性: {feasibility}
创新点数: {n_innovation}
Baseline数: {n_baseline}

输出JSON:
{{"optimization_paths":[{{"direction":"...","expected_gain":"...","difficulty":"低|中|高","action_items":["..."]}}],
"degradation_paths":[{{"path":"...","trade_off":"...","survival_rate":"高|中|极高"}}],
"risk_mitigation":["..."]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, feasibility: dict[str, Any], n_innovation: int, n_baseline: int) -> dict[str, str]:
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], feasibility=feasibility.get("verdict", "unknown"),
        n_innovation=n_innovation, n_baseline=n_baseline)}
