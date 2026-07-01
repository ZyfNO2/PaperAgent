"""API for topic research main flow (Session 66)."""
from fastapi import APIRouter
from app.services.topic_research_flow import (
    TopicResearchStartRequest,
    TopicResearchFlowResult,
    start_topic_research,
)

router = APIRouter(prefix="/api/v1/topic-research", tags=["topic-research"])


@router.post("/start", response_model=TopicResearchFlowResult)
async def post_start(request: TopicResearchStartRequest) -> TopicResearchFlowResult:
    """Start research flow.

    Returns TopicResearchFlowResult with step=keywords_ready.
    Does NOT trigger retrieval. Does NOT return old AnalysisResponse.
    """
    return start_topic_research(request)
