"""Devil's advocate prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = ("你是论文开题审查员。5维评分。判断标准: "
          "有baseline+有创新点+有工作包→ACCEPT。创新点缺细节是正常的→MINOR_REVISION。"
          "BLOCK仅用于编造证据或baseline完全缺失。只输出JSON。")

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
- 有baseline>=1 + 有创新点 + 有工作包 -> ACCEPT
- 有baseline>=1 + 创新点描述模糊或工作包不完整 -> MINOR_REVISION
- 有baseline>=1 但无创新点 -> MINOR_REVISION
- 无baseline -> BLOCK
- BLOCK仅用于: 创新点引用了不存在的论文/数据集/repo (编造证据)，或baseline完全缺失

输出JSON:
{{"dimension_scores":[{{"dimension":"D1","score":0,"verdict":"PASS|WARN|BLOCK","reason":"具体原因"}}],
"overall_verdict":"ACCEPT|MINOR_REVISION|BLOCK",
"fabrication_alerts":["如有编造"],
"risks_identified":["具体风险"],
"evidence_critiques":[{{"target_type":"innovation|narrative|work_package","target_id":"innovation_0|wp-xxx|rev-0","issue":"具体问题描述","evidence_id":"引用的论文ID","severity":"critical|major|minor","suggested_fix":"具体修改建议"}}]}}

重要约束:
1. 每个 evidence_critique 必须指向具体的 target_id（innovation_序号 / wp-包名 / rev-版本号）
2. 不允许泛泛评价（如"创新点不足"），必须指出具体哪条创新点有什么问题
3. evidence_id 必须是实际存在的论文 ID
4. suggested_fix 必须是可操作的修改建议

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, feasibility: dict[str, Any], innovations: list[dict[str, Any]],
          narrative: dict[str, Any], work_packages: list[dict[str, Any]]) -> dict[str, str]:
    feas_slim = {"verdict": feasibility.get("verdict", ""),
                 "score": feasibility.get("score", 0),
                 "reason": feasibility.get("reason", "")}
    # Re7.7: defensive filter — LLM or replay may inject non-dict items
    inn_slim = [{"description": i.get("description", ""),
                 "baseline_used": i.get("baseline_used", "")}
                for i in innovations[:3] if isinstance(i, dict)]
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
