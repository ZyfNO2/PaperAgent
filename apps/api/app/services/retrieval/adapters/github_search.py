"""GitHub repo 检索 (SOP §8.4)."""

from __future__ import annotations

from typing import Any

from .._http import HttpError, fetch_with_timeout


GITHUB_API = "https://api.github.com/search/repositories"


async def github_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """从 GitHub search repos 检索原始 dict 列表.

    返回字段: ``full_name / html_url / description / stargazers_count /
    forks_count / language / license / updated_at / topics``.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PaperAgent/1.0",
    }
    results: list[dict] = []
    qs = queries[:3] if queries else []
    for q in qs:
        url = f"{GITHUB_API}?q={q}&per_page={top_k}&sort=stars&order=desc"
        try:
            data = await fetch_with_timeout(url, headers=headers, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, dict):
            continue
        for r in data.get("items") or []:
            if not isinstance(r, dict):
                continue
            r.setdefault("stars", r.get("stargazers_count"))
            results.append(r)
    return results[:top_k]