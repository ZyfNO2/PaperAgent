"""Optimization advisor prompt — Re2 enriched (TODO-1: parallel paper analysis)."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是研究方向优化顾问。基于平行论文对比给优化方向和退化路线。保毕业导向。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

可行性: {feasibility_json}

创新点数: {n_innovation}

Baseline论文:
{baselines_json}

Parallel论文(做了类似工作的论文):
{parallels_json}

任务:
1. 对比parallel论文的方法/数据集差异，找出当前题目可借鉴的方向
2. 基于 feasibility verdict 给优化路径或退化路线
3. 给风险缓解措施

输出JSON:
{{"optimization_paths":[{{"direction":"具体方向","expected_gain":"预期收益","difficulty":"低|中|高","action_items":["具体操作"],"ref_parallel":"参考的parallel论文标题"}}],
"degradation_paths":[{{"path":"退化路线","trade_off":"代价","survival_rate":"高|中|极高"}}],
"risk_mitigation":["具体措施"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, feasibility: dict[str, Any], innovations: list[dict[str, Any]],
          baselines: list[dict[str, Any]], parallels: list[dict[str, Any]]) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""),
                 "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", "")}
                for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        feasibility_json=_json.dumps(
            {"verdict": feasibility.get("verdict", ""),
             "score": feasibility.get("score", 0)},
            ensure_ascii=False),
        n_innovation=len(innovations),
        baselines_json=_json.dumps(slim(baselines), ensure_ascii=False),
        parallels_json=_json.dumps(slim(parallels), ensure_ascii=False))}
