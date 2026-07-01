"""LLM prompt templates for the research planner agent.

Centralizes all prompt strings used by research_planner_agent.
Each function returns a formatted string ready for chat_json().
All prompts are verbatim from Session 63 SOP — do not modify text.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Domain routes (shared across prompts)
# ---------------------------------------------------------------------------
DOMAIN_ROUTES = (
    "vision_2d, vision_3d, nlp_llm, signal_timeseries, robotics_control, "
    "remote_sensing, medical_ai, energy_power, civil_infra, unknown"
)


# ---------------------------------------------------------------------------
# Schema templates (for output instructions embedded in prompts)
# ---------------------------------------------------------------------------
TOPIC_UNDERSTAND_SCHEMA = """{
  "raw_topic": str,
  "normalized_topic": str,
  "domain_route": one of [vision_2d, vision_3d, nlp_llm, signal_timeseries, robotics_control, remote_sensing, medical_ai, energy_power, civil_infra, unknown],
  "domain_confidence": float 0-1,
  "method_terms": [str],
  "task_terms": [str],
  "object_terms": [str],
  "modality_terms": [str],
  "data_terms": [str],
  "metric_terms": [str],
  "risk_terms": [str],
  "query_atoms_zh": [str],
  "query_atoms_en": [str],
  "negative_domains": [str],
  "needs_clarification": [str],
  "why_this_route": str
}"""


PROBLEM_DECOMPOSE_SCHEMA = """{
  "sub_questions": [
    {
      "id": str,
      "question": str,
      "priority": int 1-5,
      "search_intent": str,
      "required_atoms": {method: [...], task: [...], object: [...], modality: [...], data: [...], baseline: [...], risk: [...]},
      "success_signal": str,
      "failure_signal": str
    }
  ],
  "graduation_safe_path": str,
  "high_risk_path": str,
  "human_checkpoints": [str]
}"""


SEARCH_STRATEGY_SCHEMA = """{
  "topic": str,
  "domain_route": str,
  "search_strategies": [
    {
      "name": one of [core_papers, datasets, github_repos, classic_baselines, emerging_methods],
      "target_type": one of [paper, dataset, repo, baseline, tool],
      "queries": [str 3-8 words],
      "preferred_tools": [str],
      "max_results_per_query": int,
      "why": str
    }
  ],
  "negative_filters": [str],
  "source_policy": {arxiv: bool, semantic_scholar: bool, github: bool, kaggle: bool, hf_datasets: bool, papers_with_code: bool},
  "clarification_questions": [str]
}"""


CANDIDATE_SCREEN_SCHEMA = """{
  "shortlist": [
    {
      "candidate_id": str,
      "candidate_type": one of [paper, dataset, repo, baseline, tool],
      "relevance_score": float 0-1,
      "quality_score": float 0-1,
      "graduation_fit": one of [high, medium, low, none],
      "matched_atoms": [str],
      "keep_reason": str,
      "risk_reason": str,
      "must_verify": [str]
    }
  ],
  "rejected": [
    {"candidate_id": str, "reason": str}
  ],
  "need_retry_queries": [str],
  "need_human_confirmation": bool
}"""


DIRECTION_ADVICE_SCHEMA = """{
  "directions": [
    {
      "id": str,
      "title": str,
      "route_type": one of [graduation_safe, optional_enhancement, fallback],
      "graduation_fit": one of [high, medium, low],
      "confidence": float 0-1,
      "bound_evidence_ids": [str],
      "recommended_baselines": [str],
      "suggested_modules": [str],
      "why_graduation_friendly": str,
      "risk_reasons": [str],
      "user_must_confirm": [str]
    }
  ],
  "stop_reason": one of [ready, need_more_search, need_clarification, evidence_gap]
}"""


# ---------------------------------------------------------------------------
# 1. topic_understand — System prompt
# ---------------------------------------------------------------------------
def topic_understand_system() -> str:
    """System prompt for topic understanding / normalization."""
    return (
        "你是面向中国工科毕业论文选题的科研规划助手。你的任务是把一个自然语言题目拆成可检索、可验证、可追问的结构化 topic spec。\n"
        "\n"
        "你必须遵守：\n"
        "1. 不要编造论文、数据集、GitHub 项目或实验结果。\n"
        "2. 你只能做题目理解和检索规划，不生成候选证据。\n"
        "3. 不要因为题目含\"检测/智能/深度学习\"就默认归入 YOLO、U-Net、PointNet 或 BERT。\n"
        f"4. 必须区分 domain_route：{DOMAIN_ROUTES}。\n"
        "5. 如果题目对象不明确，必须提出 needs_clarification，而不是擅自假设。\n"
        "6. 输出必须是严格 JSON，不要输出 markdown。\n"
    )


# ---------------------------------------------------------------------------
# 2. topic_understand — User prompt
# ---------------------------------------------------------------------------
def topic_understand_user(raw_topic: str, student_context: str, local_case_hints: str) -> str:
    """User prompt for topic understanding.

    Args:
        raw_topic: Student's raw topic text.
        student_context: Student background (major, year, tools known).
        local_case_hints: Local case hints (e.g., school lab access, datasets known).
    """
    return (
        f"原始题目：\n{raw_topic}\n"
        f"\n"
        f"学生背景：\n{student_context}\n"
        f"\n"
        f"本地/案例提示：\n{local_case_hints}\n"
        f"\n"
        f"请输出严格 JSON，结构如下：\n"
        f"{TOPIC_UNDERSTAND_SCHEMA}\n"
    )


# ---------------------------------------------------------------------------
# 3. problem_decompose — System prompt
# ---------------------------------------------------------------------------
def problem_decompose_system() -> str:
    """System prompt for sub-question decomposition."""
    return (
        "你是 senior research strategist，负责把工科毕业选题拆成可检索、可验证、可毕业的子问题。\n"
        "\n"
        "你必须：\n"
        "1. 输出至少 4 个 prioritized sub_questions。\n"
        "2. 每个 sub_question 必须关联 method/task/object/modality/data/baseline/risk 中至少 2 类。\n"
        "3. 不允许生成论文候选或具体引用。\n"
        "4. 不允许扩大到全自动写论文或实验计划。\n"
        "5. 必须把\"保底毕业路线\"和\"高风险创新路线\"分开。\n"
    )


# ---------------------------------------------------------------------------
# 4. problem_decompose — User prompt
# ---------------------------------------------------------------------------
def problem_decompose_user(topic_parse_json: str) -> str:
    """User prompt for sub-question decomposition.

    Args:
        topic_parse_json: JSON string of topic parse output from topic_understand.
    """
    return (
        f"输入 topic_parse：\n{topic_parse_json}\n"
        f"\n"
        f"请输出严格 JSON，结构如下：\n"
        f"{PROBLEM_DECOMPOSE_SCHEMA}\n"
    )


# ---------------------------------------------------------------------------
# 5. search_strategy — System prompt
# ---------------------------------------------------------------------------
def search_strategy_system() -> str:
    """System prompt for search strategy generation."""
    return (
        "你设计科研检索策略和工具调用计划。目标是覆盖论文、数据集、工程仓库、baseline、经典工具和新锐方法。\n"
        "\n"
        "你必须遵守：\n"
        "1. 不生成候选论文/数据集/仓库，只生成搜索计划。\n"
        "2. 所有实际检索 query 只能出现在 search_strategies[].queries。\n"
        "3. 每条 query 必须是 3-8 个词的短字符串，优先英文，必要时附中文。\n"
        "4. 至少 5 个 strategy：core_papers, datasets, github_repos, classic_baselines, emerging_methods。\n"
        "5. 每个 strategy 3-6 条 query。\n"
        "6. 必须包含 negative_filters，用于过滤明显错误领域。\n"
        "7. 如果领域不确定，必须增加 clarification_questions。\n"
    )


# ---------------------------------------------------------------------------
# 6. search_strategy — User prompt
# ---------------------------------------------------------------------------
def search_strategy_user(topic_parse_json: str, problem_decompose_json: str) -> str:
    """User prompt for search strategy generation.

    Args:
        topic_parse_json: JSON string of topic parse output.
        problem_decompose_json: JSON string of problem decompose output.
    """
    return (
        f"topic_parse：\n{topic_parse_json}\n"
        f"\n"
        f"problem_decompose：\n{problem_decompose_json}\n"
        f"\n"
        f"请输出严格 JSON，结构如下：\n"
        f"{SEARCH_STRATEGY_SCHEMA}\n"
    )


# ---------------------------------------------------------------------------
# 7. candidate_screen — System prompt
# ---------------------------------------------------------------------------
def candidate_screen_system() -> str:
    """System prompt for candidate screening."""
    return (
        "你是严格的领域相关性审稿人。你只能筛选输入中已经存在的真实候选，不允许新增、改名、补充不存在的论文/数据集/仓库。\n"
        "\n"
        "你必须：\n"
        "1. 拒绝跨领域误命中，即使关键词相似。\n"
        "2. 区分 paper/dataset/repo/baseline/tool。\n"
        "3. 对每个保留候选给出 matched_atoms、keep_reason、risk_reason、graduation_fit。\n"
        "4. 如果所有候选都不相关，返回空 shortlist，并要求重新检索或人工确认。\n"
    )


# ---------------------------------------------------------------------------
# 8. candidate_screen — User prompt
# ---------------------------------------------------------------------------
def candidate_screen_user(topic_parse_json: str, candidates_jsonl: str) -> str:
    """User prompt for candidate screening.

    Args:
        topic_parse_json: JSON string of topic parse output.
        candidates_jsonl: JSONL string of raw candidates from retrieval.
    """
    return (
        f"topic_parse：\n{topic_parse_json}\n"
        f"\n"
        f"候选列表（JSONL，每行一条）：\n{candidates_jsonl}\n"
        f"\n"
        f"请输出严格 JSON，结构如下：\n"
        f"{CANDIDATE_SCREEN_SCHEMA}\n"
    )


# ---------------------------------------------------------------------------
# 9. direction_advice — System prompt
# ---------------------------------------------------------------------------
def direction_advice_system() -> str:
    """System prompt for graduation-friendly direction advice."""
    return (
        "你是毕业论文选题顾问。你只能基于已经检索和筛选过的候选证据给出方向建议。\n"
        "\n"
        "你必须：\n"
        "1. 给出 1 个保底毕业方向、1-2 个可选增强方向、1 个降级路线。\n"
        "2. 每个方向必须绑定 paper/dataset/repo/baseline/tool 中至少 2 类证据；证据不足时必须标 evidence_gap。\n"
        "3. 不生成完整开题报告。\n"
        "4. 不承诺 SOTA，不虚构实验结果。\n"
        "5. 解释为什么适合毕业、为什么可能不适合、需要用户确认什么。\n"
    )


# ---------------------------------------------------------------------------
# 10. direction_advice — User prompt
# ---------------------------------------------------------------------------
def direction_advice_user(topic_parse_json: str, shortlist_json: str, gap_report_json: str) -> str:
    """User prompt for direction advice.

    Args:
        topic_parse_json: JSON string of topic parse output.
        shortlist_json: JSON string of screened shortlist.
        gap_report_json: JSON string of evidence gap report.
    """
    return (
        f"topic_parse：\n{topic_parse_json}\n"
        f"\n"
        f"候选 shortlist：\n{shortlist_json}\n"
        f"\n"
        f"evidence gap report：\n{gap_report_json}\n"
        f"\n"
        f"请输出严格 JSON，结构如下：\n"
        f"{DIRECTION_ADVICE_SCHEMA}\n"
    )