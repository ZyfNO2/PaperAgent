"""OpenAlex paper 检索 (SOP §8.1).

生产实现用 ``https://api.openalex.org/works?search=...``, 但本模块优先
支持 ``client`` 注入 (测试用), 缺 client 时走 ``fetch_with_timeout``.
所有失败抛 ``HttpError``, 由 orchestrator 捕获.

性能说明: 只跑 queries[0] (一条主查询), 避免重复返回同源候选.
"""

from __future__ import annotations

from typing import Any

from .._http import HttpError, fetch_with_timeout


OPENALEX_API = "https://api.openalex.org/works"


def _to_oa_query(query: str) -> str:
    return query.replace(" ", "+")


async def openalex_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
    per_page: int | None = None,
) -> list[dict]:
    """从 OpenAlex 检索 paper 原始 dict 列表."""

    per_page = per_page or top_k
    headers = {
        "User-Agent": "PaperAgent/1.0 (mailto:[email protected])",
        "Accept": "application/json",
    }
    results: list[dict] = []

    qs = queries[:1] if queries else []
    for q in qs:
        url = f"{OPENALEX_API}?search={_to_oa_query(q)}&per_page={per_page}"
        try:
            data = await fetch_with_timeout(url, headers=headers, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, dict):
            continue
        for r in data.get("results") or []:
            if not isinstance(r, dict):
                continue
            rid = r.get("id")
            if isinstance(rid, str) and rid.startswith("https://openalex.org/"):
                rid = rid.rsplit("/", 1)[-1]
            r["openalex_id"] = str(rid) if rid else None
            results.append(r)

    return results[: max(top_k, per_page)]
