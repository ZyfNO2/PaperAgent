"""Semantic Scholar 检索占位 (SOP §8.2 / §19 降级)."""

from __future__ import annotations

from typing import Any


async def semantic_scholar_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Semantic Scholar paper 检索占位.

    MVP 默认返回空列表, 保留 adapter 入口供后续 S15 / S16 接入.
    """

    _ = (queries, top_k, client)
    return []


async def kaggle_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Kaggle 检索占位 (SOP §8.6)."""

    _ = (queries, top_k, client)
    return []