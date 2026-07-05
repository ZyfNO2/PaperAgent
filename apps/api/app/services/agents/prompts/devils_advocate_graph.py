"""Devil's advocate prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any

SYSTEM = "你是论文开题审查员。5维评分。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
可行性: {feasibility}
创新点: {innovations}
叙事: {narrative}
工作包: {work_packages}

5维评分(0-10): D1原创性 D2方法学 D3证据充分性 D4论证连贯 D5写作质量
输出JSON:
{{"dimension_scores":[{{"dimension":"D1","score":0,"verdict":"PASS|WARN|BLOCK","reason":"..."}}],
"overall_verdict":"ACCEPT|MINOR_REVISION|BLOCK","fabrication_alerts":[],"risks_identified":[]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, feasibility: dict[str, Any], innovations: list[dict[str, Any]],
          narrative: dict[str, Any], work_packages: list[dict[str, Any]]) -> dict[str, str]:
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:100],
        feasibility=str(feasibility.get("verdict", ""))[:50],
        innovations=str(innovations[:2])[:200],
        narrative=str(narrative.get("narrative_summary", ""))[:200],
        work_packages=str(work_packages[:2])[:200])}
