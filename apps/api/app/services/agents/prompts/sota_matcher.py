"""SOTA matcher prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是实验设计顾问。选SOTA对比论文+给消融建议。保毕业档。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文(可选对比基线):
{baselines_json}

任务:
1. 选3篇作为对比基线
2. 推荐对比指标
3. 给3个消融实验建议
4. 给实验检查清单

输出JSON:
{{"comparison_papers":[{{"title":"论文标题","year":"年份","reason":"为什么选它对比"}}],
"metrics_to_compare":["指标名"],
"ablation_suggestions":[{{"name":"消融实验名","purpose":"验证什么","expected_drop":"预期降幅"}}],
"experiment_checklist":["实验项"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]]) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""),
                 "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", ""),
                 "venue": i.get("venue", i.get("source", ""))}
                for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        baselines_json=_json.dumps(slim(baselines), ensure_ascii=False))}
