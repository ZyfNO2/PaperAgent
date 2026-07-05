"""Innovation extractor prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是学术裁缝专家。从baseline和parallel中提取可缝合模块。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline论文: {baselines}
Parallel论文: {parallels}

分析每个baseline用了什么方法组件，每个parallel做了什么改进。
输出JSON:
{{"innovation_points":[{{"description":"...","baseline_used":"...","stitched_modules":["..."],"stitching_plan":"...","estimated_difficulty":"低|中|高"}}],
"stitching_plan":{{"baseline_model":"...","module_b":"...","module_c":"...","stitching_steps":["1. ..."],"risk_notes":[]}}}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]], parallels: list[dict[str, Any]]) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""), "source": i.get("source", "")} for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], baselines=_json.dumps(slim(baselines), ensure_ascii=False),
        parallels=_json.dumps(slim(parallels), ensure_ascii=False))}
