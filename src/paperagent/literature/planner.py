from __future__ import annotations

from paperagent.schemas import ResearchPlan
from paperagent.schemas.literature import LiteratureQueryPlan, QueryLane, QueryPurpose


def _purpose(text: str) -> QueryPurpose:
    value = text.lower()
    if any(token in value for token in ("failure", "limitation", "error", "risk")):
        return "limitation_failure"
    if any(token in value for token in ("method", "approach", "algorithm")):
        return "method"
    if any(token in value for token in ("dataset", "benchmark", "corpus")):
        return "benchmark_dataset"
    if any(token in value for token in ("metric", "evaluation", "measure")):
        return "evaluation_metric"
    if any(token in value for token in ("recent", "latest", "progress", "state of the art")):
        return "recent_progress"
    if any(token in value for token in ("contradict", "conflict", "opposing")):
        return "contradictory_evidence"
    if "baseline" in value:
        return "baseline"
    return "method"


def _source_preferences(text: str) -> list[str]:
    value = text.lower()
    if any(token in value for token in ("preprint", "arxiv", "recent", "latest")):
        return ["openalex", "arxiv"]
    return ["openalex", "semantic_scholar"]


def plan_literature_queries(
    plan: ResearchPlan,
    *,
    question: str,
) -> LiteratureQueryPlan:
    if plan.status != "ready":
        raise ValueError("literature query planning requires a ready research plan")
    gap_by_id = {gap.gap_id: gap for gap in plan.evidence_gaps}
    required_gap_ids = [gap.gap_id for gap in plan.evidence_gaps if gap.required]
    lanes: list[QueryLane] = []
    covered: set[str] = set()
    for query in plan.search_queries:
        if len(lanes) >= 4:
            break
        gap = gap_by_id.get(query.gap_id)
        description = gap.description if gap is not None else ""
        combined = f"{query.query} {description}"
        lanes.append(
            QueryLane(
                lane_id=query.query_id,
                purpose=_purpose(combined),
                query=query.query,
                source_preferences=_source_preferences(combined),
                gap_ids=[query.gap_id],
                priority=80 if query.gap_id in required_gap_ids else 50,
            )
        )
        covered.add(query.gap_id)
    for gap_id in required_gap_ids:
        if gap_id in covered or len(lanes) >= 4:
            continue
        gap = gap_by_id[gap_id]
        combined = f"{question} {gap.description}"
        lanes.append(
            QueryLane(
                lane_id=f"gap-{gap_id}",
                purpose=_purpose(combined),
                query=combined,
                source_preferences=_source_preferences(combined),
                gap_ids=[gap_id],
                priority=90,
            )
        )
    return LiteratureQueryPlan(
        question=question,
        scope=plan.scope,
        query_lanes=lanes,
        required_gap_ids=required_gap_ids,
        max_rounds=2,
    )
