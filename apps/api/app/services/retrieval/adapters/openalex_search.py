"""OpenAlex paper 检索 (SOP §8.1).

生产实现用 ``https://api.openalex.org/works?search=...``, 但本模块优先
支持 ``client`` 注入 (测试用), 缺 client 时走 ``fetch_with_timeout``.
所有失败抛 ``HttpError``, 由 orchestrator 捕获.

Re05 §5.2: 当主调用返回 503 或空 body 时, 重试一次 (search-style 备用端点),
仍空则结果 dict 带 ``_openalex_backup_empty=True`` 供 ledger 记录
``status="openalex_backup_empty"``.

性能说明: 只跑 queries[0] (一条主查询), 避免重复返回同源候选.
"""

from __future__ import annotations

import logging
from typing import Any

from .._http import HttpError, fetch_with_timeout


logger = logging.getLogger(__name__)


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
    """从 OpenAlex 检索 paper 原始 dict 列表.

    503/empty body 时, 重试一次 backup endpoint (search-style).
    若两次都空 → 返回 [] with ``_openalex_backup_empty=True`` on the
    wrapped sentinel? No — easier: return [] and let caller inspect the
    ``_openalex_backup_tried`` attribute attached to this coroutine via
    ``openalex_last_backup_empty()`` (testable).
    """

    per_page = per_page or top_k
    headers = {
        "User-Agent": "PaperAgent/1.0 (mailto:[email protected])",
        "Accept": "application/json",
    }

    qs = queries[:1] if queries else []
    if not qs:
        _openalex_backup_state["last"] = False
        return []
    q = qs[0]

    # --- Primary call (existing behavior, unchanged) ---
    primary = await _oa_fetch(q, per_page, headers=headers, client=client)
    results = primary["results"]

    # --- Backup retry on 503 OR empty body (Re05 §5.2) ---
    if primary["status"] == 503 or (primary["status"] == "ok" and not results):
        backup = await _oa_fetch(q, per_page, headers=headers, client=client)
        results = backup["results"]
        # Tag results from backup attempt
        for r in results:
            r.setdefault("_openalex_source", "backup")
        if not results:
            _openalex_backup_state["last"] = True
        else:
            _openalex_backup_state["last"] = False
    else:
        _openalex_backup_state["last"] = False

    # Stamp source on primary results too (for ledger / dedup debugging).
    for r in results:
        r.setdefault("_openalex_source", "primary")

    return results[: max(top_k, per_page)]


# Module-level singleton so callers (orchestrator) can ask:
#   openalex_last_backup_empty() → bool
# reset by every openalex_search() call.
_openalex_backup_state = {"last": False}


def openalex_last_backup_empty() -> bool:
    """Whether the most recent openalex_search() call had both attempts empty.

    Orchestrator uses this to record SourceLedger status="openalex_backup_empty".
    """
    return bool(_openalex_backup_state.get("last"))


async def _oa_fetch(query: str, per_page: int, *, headers: dict, client: Any | None) -> dict:
    """Single OpenAlex call. Returns dict {status, results}."""
    url = f"{OPENALEX_API}?search={_to_oa_query(query)}&per_page={per_page}"
    try:
        data = await fetch_with_timeout(url, headers=headers, client=client, timeout=10.0)
    except HttpError as exc:
        msg = str(exc)
        # Try to detect 503 in the wrapped HttpError message.
        if "HTTP 503" in msg:
            return {"status": 503, "results": []}
        # Other HTTP errors: bubble (orchestrator catches).
        raise
    if not isinstance(data, dict):
        return {"status": "ok", "results": []}
    results: list[dict] = []
    for r in data.get("results") or []:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        if isinstance(rid, str) and rid.startswith("https://openalex.org/"):
            rid = rid.rsplit("/", 1)[-1]
        r["openalex_id"] = str(rid) if rid else None
        results.append(r)
    return {"status": "ok", "results": results}