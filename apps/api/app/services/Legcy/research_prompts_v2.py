"""Prompt overlays and new schemas for the structured research agent.

Keeps Session 63 prompts untouched while allowing stricter V2 behavior for:
- tool planning
- scientific-style output normalization
- non-hallucinatory candidate grouping
"""

from __future__ import annotations

from . import research_prompts as v1


TOOL_PLAN_SCHEMA = """{
  "topic_atoms": {
    "raw": str,
    "domain_route": str,
    "method_terms": [str],
    "task_terms": [str],
    "object_terms": [str]
  },
  "calls": [
    {
      "call_id": str,
      "tool": one of [search_openalex, search_arxiv, search_github, search_dataset_web, search_paperswithcode, fetch_url_metadata],
      "target": one of [paper, dataset, repo, baseline, module_paper],
      "query": str,
      "when_to_call": str,
      "why_call": str,
      "how_call": {"top_k": int},
      "expected_output": str,
      "stop_condition": str
    }
  ],
  "human_gate_after": str
}"""


SCIENTIFIC_STYLE_RULES = (
    "你必须尽量贴近科研 Skill 风格：\n"
    "1. 不抢答结论，不生成虚构论文/数据集/仓库。\n"
    "2. baseline 与 平行参考必须区分，不能混成一个列表。\n"
    "3. repo/dataset 只能来自真实检索结果，找不到就明确写未找到或待人工确认。\n"
    "4. 任何建议都要建立在真实 shortlist 上，证据不足时先写缺口。\n"
)


def topic_understand_system() -> str:
    return v1.topic_understand_system() + "\n" + SCIENTIFIC_STYLE_RULES


def problem_decompose_system() -> str:
    return v1.problem_decompose_system() + "\n" + SCIENTIFIC_STYLE_RULES


def search_strategy_system() -> str:
    return v1.search_strategy_system() + "\n" + SCIENTIFIC_STYLE_RULES


def candidate_screen_system() -> str:
    return v1.candidate_screen_system() + "\n" + SCIENTIFIC_STYLE_RULES


def direction_advice_system() -> str:
    return v1.direction_advice_system() + "\n" + SCIENTIFIC_STYLE_RULES


def tool_plan_system() -> str:
    return (
        "你是结构化 research planner。你只能生成工具调用计划，不能生成候选结论。\n"
        "只允许使用白名单工具：search_openalex, search_arxiv, search_github, "
        "search_dataset_web, search_paperswithcode, fetch_url_metadata。\n"
        "每个 call 只做一件事，query 必须简洁，不能把候选标题写进 query 以外字段。\n"
        "优先保证论文 / repo / dataset 三类覆盖；证据不足时允许保留 gap，但不准伪造候选。\n"
        "输出必须是严格 JSON。\n"
    )


def tool_plan_user(topic_parse_json: str, search_strategy_json: str) -> str:
    return (
        f"topic_parse:\n{topic_parse_json}\n\n"
        f"search_strategy:\n{search_strategy_json}\n\n"
        f"请输出严格 JSON，结构如下：\n{TOOL_PLAN_SCHEMA}\n"
    )

