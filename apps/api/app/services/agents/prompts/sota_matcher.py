"""SOTA matcher prompt — Re1.4 MVP."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是实验设计顾问。选SOTA对比论文+给消融建议。保毕业档。只输出JSON。"

USER_TEMPLATE = """题目: {topic}
Baseline论文: {baselines}

选3篇作为对比基线，给3个消融实验建议。
输出JSON:
{{"comparison_papers":[{{"title":"...","year":"..."}}],
"metrics_to_compare":["Accuracy","F1"],
"ablation_suggestions":[{{"name":"去掉模块B","purpose":"...","expected_drop":"1-3%"}}],
"experiment_checklist":["对比实验","消融实验","定性分析"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]]) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""), "year": i.get("year", "")} for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200], baselines=_json.dumps(slim(baselines), ensure_ascii=False))}
