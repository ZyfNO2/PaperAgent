"""Devil's advocate prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是论文开题审查员。5维评分。根据证据充分性区分verdict。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

可行性报告:
{feasibility_json}

创新点:
{innovations_json}

叙事:
{narrative_json}

工作包:
{work_packages_json}

5维评分(0-10):
- D1原创性: 是否真的发现了gap，还是硬凑
- D2方法学严谨性: baseline选择是否合理
- D3证据充分性: baseline>=2 + parallel>=2 + dataset>=1 -> PASS; 否则 WARN/BLOCK
- D4论证连贯性: 3个问题是否真的被模块解决
- D5写作质量: 叙事是否自洽，有无过度宣传

verdict判定规则:
- 有baseline>=2 + work_package>=1 -> ACCEPT 或 MINOR_REVISION
- 有baseline>=1 但work_package=0 -> MINOR_REVISION
- 无baseline -> BLOCK

输出JSON:
{{"dimension_scores":[{{"dimension":"D1","score":0,"verdict":"PASS|WARN|BLOCK","reason":"具体原因"}}],
"overall_verdict":"ACCEPT|MINOR_REVISION|BLOCK",
"fabrication_alerts":["如有编造"],
"risks_identified":["具体风险"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, feasibility: dict[str, Any], innovations: list[dict[str, Any]],
          narrative: dict[str, Any], work_packages: list[dict[str, Any]]) -> dict[str, str]:
    feas_slim = {"verdict": feasibility.get("verdict", ""),
                 "score": feasibility.get("score", 0),
                 "reason": feasibility.get("reason", "")}
    inn_slim = [{"description": i.get("description", ""),
                 "baseline_used": i.get("baseline_used", "")}
                for i in innovations[:3]]
    nar_slim = {"three_problems": narrative.get("three_problems", []),
                "nick_model_name": narrative.get("nick_model_name", ""),
                "narrative_summary": narrative.get("narrative_summary", "")}
    wp_slim = [{"title": w.get("title", ""),
                "description": w.get("description", "")}
               for w in work_packages[:3]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        feasibility_json=_json.dumps(feas_slim, ensure_ascii=False),
        innovations_json=_json.dumps(inn_slim, ensure_ascii=False),
        narrative_json=_json.dumps(nar_slim, ensure_ascii=False),
        work_packages_json=_json.dumps(wp_slim, ensure_ascii=False))}
