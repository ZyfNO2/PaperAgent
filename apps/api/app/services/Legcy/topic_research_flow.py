"""Session 66: 主链路流程状态机.
封装 题目 -> 关键词 -> 检索 -> 清洗 -> 角色 -> baseline -> 工作建议.
"""
from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel


MainFlowStep = Literal[
    "topic_ready",
    "keywords_ready",
    "retrieval_ready",
    "baseline_required",
    "work_package_ready",
    "blocked",
]

WorkPackageStatus = Literal["not_started", "needs_baseline_selection", "need_more_search", "ok"]


class TopicResearchStartRequest(BaseModel):
    raw_topic: str
    project_id: str | None = None
    mode: str = "mvp"


class TopicResearchFlowResult(BaseModel):
    project_id: str
    run_id: str | None = None
    topic: str
    step: MainFlowStep
    keywords: dict | None = None
    retrieval_run_summary: dict | None = None
    selected_baseline_ids: list[str] = []
    work_package_status: WorkPackageStatus = "not_started"
    user_next_action: str
    progress_events: list[dict] = []


def start_topic_research(request: TopicResearchStartRequest) -> TopicResearchFlowResult:
    """Start research flow: create project_id, parse keywords, return flow state.

    Does NOT call /one-topic/analyze, does NOT return old AnalysisResponse.
    """
    from app.services.research_topic_parser import parse_topic_rule_based

    project_id = request.project_id or f"ot_{uuid.uuid4().hex[:12]}"

    # Parse keywords using rule-based parser
    parsed = parse_topic_rule_based(request.raw_topic)

    return TopicResearchFlowResult(
        project_id=project_id,
        topic=request.raw_topic,
        step="keywords_ready",
        keywords=parsed,
        user_next_action="请确认关键词后点击'确认并检索'",
        progress_events=[
            {"step": "topic_parsed", "domain": parsed.get("detected_domain", "unknown")},
        ],
    )
