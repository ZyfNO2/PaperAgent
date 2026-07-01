"""Session 63 T4: Unified research tool router.

所有 paper/dataset/repo/local_rag/trace 工具调用必须经过本模块,
trace 事件统一在 router 层写, adapter / service 层不再直写 trace.

对外接口:
    search_papers(queries, sources, top_k_per_query)
    search_datasets(queries, sources, top_k_per_query)
    search_repos(queries, min_stars, top_k_per_query)
    local_rag_search(query, project_id, top_k)
    trace_write_event(event_type, event_data, project_id)

失败处理:
    单 source 抛错 → 记 tool_call_failed, 跳过该 source, 不让其他 source 受影响
    全部 source 都空 → 返回 [], 不抛
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from .retrieval.adapters import arxiv_search, github_search, huggingface_search, openalex_search
from .retrieval.adapters.optional_adapters import kaggle_search
from .paper_library.local_rag import ask_local_rag
from .trace_store import append_trace


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 支持的 trace event 类型 (用于校验 event_data 字段)
# ---------------------------------------------------------------------------


TRACE_EVENTS: dict[str, set[str]] = {
    "topic_parse_started": {"raw_topic", "phase"},
    "topic_parse_completed": {"raw_topic", "domain_route", "needs_clarification_count"},
    "human_checkpoint_waiting": {"checkpoint", "editable_fields"},
    "human_checkpoint_confirmed": {"checkpoint", "user_changes"},
    "search_strategy_created": {"strategy_count", "query_count", "domain_route"},
    "tool_call_started": {"tool_name", "query", "source"},
    "tool_call_completed": {"tool_name", "query", "source", "result_count"},
    "tool_call_failed": {"tool_name", "query", "source", "failed_reason"},
    "candidate_screen_completed": {"input_count", "kept_count", "rejected_count"},
    "evidence_gap_detected": {"missing_types", "retry_queries"},
    "direction_advice_ready": {"direction_count", "best_route", "confidence"},
}


# ---------------------------------------------------------------------------
# source → adapter 映射
# ---------------------------------------------------------------------------


_PAPER_SOURCES: dict[str, Any] = {
    "arxiv": arxiv_search,
    "openalex": openalex_search,
}


_DATASET_SOURCES: dict[str, Any] = {
    "huggingface": huggingface_search,
    "kaggle": kaggle_search,
}


# ---------------------------------------------------------------------------
# 内部: run one source with trace + error handling
# ---------------------------------------------------------------------------


async def _run_source(
    project_id: str,
    tool_name: str,
    source: str,
    fn: Any,
    queries: list[str],
    top_k: int,
) -> list[dict]:
    """Run single source with started/completed/failed trace events.

    Failure on this source: log + trace tool_call_failed, return [].
    Other sources keep running.
    """

    query = queries[0] if queries else ""
    trace_write_event(
        "tool_call_started",
        {"tool_name": tool_name, "query": query, "source": source},
        project_id=project_id,
    )

    try:
        result = await fn(queries, top_k)
    except Exception as exc:
        logger.warning("[%s/%s] failed: %s", tool_name, source, exc)
        trace_write_event(
            "tool_call_failed",
            {"tool_name": tool_name, "query": query, "source": source, "failed_reason": str(exc)},
            project_id=project_id,
        )
        return []

    results = result if isinstance(result, list) else []
    trace_write_event(
        "tool_call_completed",
        {"tool_name": tool_name, "query": query, "source": source, "result_count": len(results)},
        project_id=project_id,
    )
    return results


# ---------------------------------------------------------------------------
# 对外: search_papers
# ---------------------------------------------------------------------------


async def search_papers(
    queries: list[str],
    sources: list[str] | None = None,
    top_k_per_query: int = 8,
    project_id: str = "",
) -> list[dict]:
    """Search real paper sources.

    默认 sources: ["arxiv", "openalex"].
    单 source 失败不影响其他 source. 全部空返回 [].
    """

    sources = sources or ["arxiv", "openalex"]
    if not queries:
        return []

    project_id = project_id or "_anonymous"

    tasks = []
    for src in sources:
        fn = _PAPER_SOURCES.get(src)
        if fn is None:
            logger.warning("unknown paper source: %s", src)
            continue
        tasks.append(_run_source(project_id, "search_papers", src, fn, queries, top_k_per_query))

    if not tasks:
        return []
    nested = await asyncio.gather(*tasks)
    out: list[dict] = []
    for r in nested:
        out.extend(r)
    return out


# ---------------------------------------------------------------------------
# 对外: search_datasets
# ---------------------------------------------------------------------------


async def search_datasets(
    queries: list[str],
    sources: list[str] | None = None,
    top_k_per_query: int = 5,
    project_id: str = "",
) -> list[dict]:
    """Search dataset registries.

    默认 sources: ["huggingface", "kaggle"].
    """

    sources = sources or ["huggingface", "kaggle"]
    if not queries:
        return []

    project_id = project_id or "_anonymous"

    tasks = []
    for src in sources:
        fn = _DATASET_SOURCES.get(src)
        if fn is None:
            logger.warning("unknown dataset source: %s", src)
            continue
        tasks.append(_run_source(project_id, "search_datasets", src, fn, queries, top_k_per_query))

    if not tasks:
        return []
    nested = await asyncio.gather(*tasks)
    out: list[dict] = []
    for r in nested:
        out.extend(r)
    return out


# ---------------------------------------------------------------------------
# 对外: search_repos
# ---------------------------------------------------------------------------


async def search_repos(
    queries: list[str],
    min_stars: int = 20,
    top_k_per_query: int = 8,
    project_id: str = "",
) -> list[dict]:
    """Search GitHub repositories. Filter by min_stars client-side.

    github adapter 按 stars desc 排序, top_k_per_query 截断后, 这里再过
    一道 min_stars 过滤. min_stars 影响 result_count, 不改 adapter.
    """

    if not queries:
        return []

    project_id = project_id or "_anonymous"

    query = queries[0] if queries else ""
    trace_write_event(
        "tool_call_started",
        {"tool_name": "search_repos", "query": query, "source": "github"},
        project_id=project_id,
    )

    try:
        raw = await github_search(queries, top_k_per_query)
    except Exception as exc:
        logger.warning("[search_repos/github] failed: %s", exc)
        trace_write_event(
            "tool_call_failed",
            {"tool_name": "search_repos", "query": query, "source": "github", "failed_reason": str(exc)},
            project_id=project_id,
        )
        return []

    filtered: list[dict] = []
    for r in raw if isinstance(raw, list) else []:
        stars = r.get("stars") or r.get("stargazers_count") or 0
        if isinstance(stars, int) and stars >= min_stars:
            filtered.append(r)

    trace_write_event(
        "tool_call_completed",
        {"tool_name": "search_repos", "query": query, "source": "github", "result_count": len(filtered)},
        project_id=project_id,
    )
    return filtered


# ---------------------------------------------------------------------------
# 对外: local_rag_search
# ---------------------------------------------------------------------------


def local_rag_search(
    query: str,
    project_id: str = "",
    top_k: int = 5,
) -> list[dict]:
    """Query local paper library RAG.

    Returns list of dicts with paper_id / chunk_id / quote / score / text.
    同步接口 — ask_local_rag 本身是 sync.
    """

    if not query or not query.strip():
        return []
    if not project_id:
        return []

    trace_write_event(
        "tool_call_started",
        {"tool_name": "local_rag_search", "query": query, "source": "local"},
        project_id=project_id,
    )

    try:
        outcome = ask_local_rag(project_id=project_id, question=query, top_k=top_k)
    except Exception as exc:
        logger.warning("[local_rag_search] failed: %s", exc)
        trace_write_event(
            "tool_call_failed",
            {"tool_name": "local_rag_search", "query": query, "source": "local", "failed_reason": str(exc)},
            project_id=project_id,
        )
        return []

    results: list[dict] = []
    for ref in outcome.evidence_refs:
        results.append({
            "paper_id": ref.paper_id,
            "chunk_id": ref.chunk_id,
            "section_title": ref.section_title,
            "chunk_type": ref.chunk_type,
            "page_start": ref.page_start,
            "page_end": ref.page_end,
            "quote": ref.quote,
            "score": ref.score,
        })

    trace_write_event(
        "tool_call_completed",
        {"tool_name": "local_rag_search", "query": query, "source": "local", "result_count": len(results)},
        project_id=project_id,
    )
    return results


# ---------------------------------------------------------------------------
# 对外: trace_write_event
# ---------------------------------------------------------------------------


def trace_write_event(event_type: str, event_data: dict, project_id: str) -> None:
    """Write a trace event to trace_store.

    TRACE_EVENTS dict 列出了每个 event_type 期望的字段. 这里不强制 —
    写动作交给 append_trace, event_data 进入 after 字段.
    """

    if not project_id:
        project_id = "_anonymous"
    if event_type not in TRACE_EVENTS:
        logger.debug("unknown trace event type: %s", event_type)

    payload = dict(event_data or {})
    append_trace(
        project_id=project_id,
        action=event_type,
        target_type="research_tool",
        target_id=None,
        source="research_tool_router",
        after=payload,
    )


__all__ = [
    "TRACE_EVENTS",
    "search_papers",
    "search_datasets",
    "search_repos",
    "local_rag_search",
    "trace_write_event",
]
