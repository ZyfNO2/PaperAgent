"""Search adapter registry.

Each adapter has signature:
    async def (queries: list[str], top_k: int, *, client) -> list[dict]
"""

from __future__ import annotations

from typing import Awaitable, Callable

from ....schemas_retrieval import SearchSource
from .arxiv_search import arxiv_search
from .core_search import core_search
from .crossref_search import crossref_search
from .datacite_search import datacite_search
from .github_search import github_search
from .huggingface_search import huggingface_search
from .openalex_search import openalex_search
from .semantic_scholar_search import semantic_scholar_search


SourceFn = Callable[..., Awaitable[list[dict]]]

REGISTRY: dict[SearchSource, SourceFn] = {
    "openalex": openalex_search,
    "crossref": crossref_search,
    "arxiv": arxiv_search,
    "github": github_search,
    "huggingface": huggingface_search,
    "semantic_scholar": semantic_scholar_search,
    "core": core_search,
    "datacite": datacite_search,
}


__all__ = ["REGISTRY"]
