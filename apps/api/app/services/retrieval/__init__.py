"""S66v minimal retrieval package — only the 4 adapters our agent uses.

Legcy siblings (normalizer / dedup / ranker / orchestrator / query_plan /
...) live under `apps/api/app/services/Legcy/retrieval/` and are
NOT re-exported here.
"""

from __future__ import annotations

# Pure re-export of adapter functions so `from app.services.retrieval import
# arxiv_search` still works (older legcy imports), but the agent imports
# them directly via `from ..retrieval.adapters.arxiv_search import arxiv_search`.

from .adapters.arxiv_search import arxiv_search  # noqa: F401
from .adapters.crossref_search import crossref_search  # noqa: F401
from .adapters.github_search import github_search  # noqa: F401
from .adapters.openalex_search import openalex_search  # noqa: F401

__all__ = [
    "arxiv_search",
    "crossref_search",
    "github_search",
    "openalex_search",
]
