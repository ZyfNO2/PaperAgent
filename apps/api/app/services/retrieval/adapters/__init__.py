"""检索适配器入口 + 注册表."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ....schemas_retrieval import SearchSource
from .arxiv_search import arxiv_search
from .github_search import github_search
from .huggingface_search import huggingface_search
from .openalex_search import openalex_search
from .optional_adapters import kaggle_search, semantic_scholar_search


SourceFn = Callable[[list[str], int], Awaitable[list[dict]]]


def _make_runner(fn: SourceFn) -> SourceFn:
    """适配器统一签名 ``async def (queries, top_k, *, client) -> list[dict]``."""

    async def runner(queries: list[str], top_k: int, *, client: Any | None = None) -> list[dict]:
        return await fn(queries, top_k, client=client)

    return runner


REGISTRY: dict[SearchSource, SourceFn] = {
    "openalex": _make_runner(openalex_search),
    "arxiv": _make_runner(arxiv_search),
    "github": _make_runner(github_search),
    "huggingface": _make_runner(huggingface_search),
    "semantic_scholar": _make_runner(semantic_scholar_search),
    "kaggle": _make_runner(kaggle_search),
}


__all__ = ["REGISTRY"]