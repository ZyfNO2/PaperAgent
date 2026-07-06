"""Innovation extractor prompt — Re2 enriched."""
from __future__ import annotations
from typing import Any
import json as _json

SYSTEM = "你是学术裁缝专家。从baseline和parallel论文中提取可缝合模块。只输出JSON。"

USER_TEMPLATE = """题目: {topic}

Baseline论文(复现目标):
{baselines_json}

Parallel论文(改进参考):
{parallels_json}

任务:
1. 分析每个baseline用了什么方法组件
2. 分析每个parallel做了什么改进
3. 找出可缝合的模块组合(A+B+C方案)
4. 评估缝合难度

输出JSON:
{{"innovation_points":[{{"description":"具体创新描述","baseline_used":"baseline论文标题","stitched_modules":["模块A","模块B"],"stitching_plan":"2-3步具体操作步骤(不是抽象描述)","estimated_difficulty":"低|中|高","evidence_ref":"论文标题"}}],
"stitching_plan":{{"baseline_model":"模型名","module_b":"模块B来源","module_c":"模块C来源","stitching_steps":["1. 复现baseline(具体环境)","2. 提取模块B(从哪篇论文)","3. 拼接测试(评估方式)"],"risk_notes":["具体风险"]}}}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]], parallels: list[dict[str, Any]]) -> dict[str, str]:
    def slim(items):
        return [{"title": i.get("title", ""),
                 "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
                 "year": i.get("year", ""),
                 "venue": i.get("venue", i.get("source", ""))}
                for i in items[:5]]
    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        baselines_json=_json.dumps(slim(baselines), ensure_ascii=False),
        parallels_json=_json.dumps(slim(parallels), ensure_ascii=False))}
