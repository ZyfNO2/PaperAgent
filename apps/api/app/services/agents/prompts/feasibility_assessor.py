"""Feasibility assessor prompt — Re2.1 deep fix.

Passes paper titles + repo status so LLM can differentiate
"2 baseline with repo" vs "2 baseline without repo".
"""
from __future__ import annotations
from typing import Any

SYSTEM = ("你是开题可行性评估员。根据证据数量和内容判断能不能保毕业。"
          "不得对所有case给同一个score。只输出JSON。"
          "\n\n领域特定风险评估（必须在reason中体现）："
          "\n1. 硬件依赖：如果题目涉及机器人、机械臂、SLAM、自动驾驶、IoT——"
          "评估是否需要实物硬件（相机、传感器、机器人平台、GPU集群），"
          "学生是否能获取。在reason中提及硬件风险。"
          "\n2. 数据合规：如果题目涉及医学影像、患者数据、人体受试者、医疗——"
          "评估数据隐私、伦理审批、法规合规（HIPAA/GDPR/人类遗传资源管理）。"
          "在reason中提及合规风险。"
          "\n3. 数据集可获取性：如果题目需要专用数据集——"
          "评估公开数据集是否存在，自建数据集在论文周期内是否可行。")

USER_TEMPLATE = """题目: {topic}

Baseline论文({n_baseline}篇):
{baseline_summary}

Parallel论文({n_parallel}篇):
{parallel_summary}

数据集: {n_dataset}个, 代码仓库: {n_repo}个

评估标准 (严格按此锚点评分，不得给"安全默认值"):
- feasible (75-100分):
  - 85-100: baseline>=3 + 有数据集 + 有repo，证据链完整
  - 75-84: baseline>=1 + 有数据集或repo，但其中一项不足
- risky (40-74分):
  - 60-74: baseline>=3 但无数据集无repo（方法可复现但需自建数据）
  - 40-59: baseline<3 或涉及硬件/合规风险且无降级方案
- not_recommended (0-39分):
  - 0-39: 无baseline，或题目过于宽泛，或风险无法降级

重要: 不得对所有case给同一个score。根据baseline数量、repo有无、数据集匹配度、
领域风险给出差异化分数。有repo的比没repo的score高10-20分。
有数据集的比没数据集的score高10-15分。
涉及硬件/合规风险且无降级方案的score降10-20分。

输出JSON: {{"verdict":"feasible|risky|not_recommended","score":0-100,"reason":"<=100字，引用具体论文","100_plus_formula":{{"baseline_weight":0,"module_weights":[],"estimated_total":0,"assessment":"足够毕业|勉强|不足"}},"degradation_paths":["具体退化路线"]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(topic: str, baselines: list[dict[str, Any]], parallels: list[dict[str, Any]],
          n_dataset: int, n_repo: int) -> dict[str, str]:
    # Pass paper titles + repo status for LLM to differentiate
    baseline_summary = "\n".join(
        f"- {p.get('title', '')[:80]} (repo: {'有' if p.get('official_code_url') or p.get('url') else '无'})"
        for p in baselines[:5]
    ) or "无 baseline 论文"

    parallel_summary = "\n".join(
        f"- {p.get('title', '')[:80]}"
        for p in parallels[:5]
    ) or "无 parallel 论文"

    return {"system": SYSTEM, "user": USER_TEMPLATE.format(
        topic=topic[:200],
        n_baseline=len(baselines),
        baseline_summary=baseline_summary,
        n_parallel=len(parallels),
        parallel_summary=parallel_summary,
        n_dataset=n_dataset, n_repo=n_repo)}
