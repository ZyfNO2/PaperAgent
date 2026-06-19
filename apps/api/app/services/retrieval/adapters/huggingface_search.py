"""HuggingFace dataset 检索 (SOP §8.5)."""

from __future__ import annotations

from typing import Any

from .._http import HttpError, fetch_with_timeout


HF_API = "https://huggingface.co/api/datasets"


async def huggingface_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """从 HuggingFace datasets API 检索.

    返回字段: ``id / likes / downloads / tags / lastModified / cardData``.
    """

    results: list[dict] = []
    qs = queries[:1] if queries else []
    for q in qs:
        url = f"{HF_API}?search={q}&limit={top_k}"
        try:
            data = await fetch_with_timeout(url, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, list):
            continue
        for r in data:
            if isinstance(r, dict):
                results.append(r)
    return results[:top_k]