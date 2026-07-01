"""S66v research agent package — new run_research_agent pipeline.

See `research_agent.py` for the orchestrator and `prompts/` for the LLM
system prompts. This package is the legcy-free replacement for
`apps/api/app/services/research_planner_agent.py`.

Re02 additions: candidate_pool, source_ledger, evidence_review,
low_bar_reviewer.
"""

from .candidate_pool import (
    Candidate,
    CandidatePool,
    collect_mentioned_datasets,
    collect_papers_from_raw,
    collect_repos_from_raw,
)
from .citation_expand import citation_expand
from .evidence_review import (
    EvidenceReview,
    audit_candidates,
    by_status as reviews_by_status,
    index_by_candidate as reviews_by_candidate,
    stats as review_stats,
)
from .low_bar_reviewer import (
    LowBarVerdict,
    run_low_bar_review,
)
from .source_ledger import SourceLedger

__all__ = [
    # Re02 new modules
    "SourceLedger",
    "Candidate",
    "CandidatePool",
    "collect_papers_from_raw",
    "collect_repos_from_raw",
    "collect_mentioned_datasets",
    "EvidenceReview",
    "audit_candidates",
    "citation_expand",
    "reviews_by_status",
    "reviews_by_candidate",
    "review_stats",
    "LowBarVerdict",
    "run_low_bar_review",
]
