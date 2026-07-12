"""Narrative builder prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是论文叙事生成器。基于创新点和可行性生成3个问题+1个模型名。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

创新点:
{innovations_json}

可行性报告:
{feasibility_json}

任务:
1. 基于创新点提炼3个研究问题(每个问题必须引用具体论文)
2. 起一个模型昵称
3. 写200字叙事摘要
4. 给5章大纲

输出JSON:
{{"three_problems":[{{"problem":"问题描述","evidence":"证据","from_paper":"论文标题"}}],
"nick_model_name":"模型名",
"narrative_summary":"<=200字",
"chapter_outline":{{"chapter_1":{{"title":"绪论","sections":["研究背景","国内外现状","研究内容"]}}}},
"abstract_draft":"摘要草稿"}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, innovations: list[dict[str, Any]], feasibility: dict[str, Any]) -> dict[str, str]:
    # Re7.7: defensive filter — LLM or replay may inject non-dict items
    inn_slim = [{"description": i.get("description", ""),
                 "baseline_used": i.get("baseline_used", ""),
                 "stitched_modules": i.get("stitched_modules", [])}
                for i in innovations[:3] if isinstance(i, dict)]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        innovations_json=_json.dumps(inn_slim, ensure_ascii=False),
        feasibility_json=_json.dumps(
            {"verdict": feasibility.get("verdict", ""),
             "score": feasibility.get("score", 0),
             "reason": feasibility.get("reason", "")},
            ensure_ascii=False)[:500])}
