"""Narrative builder prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any

SYSTEM = "你是论文叙事生成器。生成3个问题+1个模型名。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
创新点: {innovations}
可行性: {feasibility}

生成叙事。
输出JSON:
{{"three_problems":[{{"problem":"...","from_paper":"..."}},{{"problem":"...","from_paper":"..."}},{{"problem":"...","from_paper":"..."}}],
"nick_model_name":"...",
"narrative_summary":"<=200字",
"chapter_outline":{{}},
"abstract_draft":""}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, innovations: list[dict[str, Any]], feasibility: dict[str, Any]) -> dict[str, str]:
    inn_text = "; ".join(i.get("description", "")[:50] for i in innovations[:3])
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], innovations=inn_text,
        feasibility=feasibility.get("verdict", "unknown"))}
