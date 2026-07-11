"""Re3.0 React-based search agent.

Replaces the fixed-adapter retrieve_node with an LLM-driven
think→call→observe loop. Inspired by ARC's SEARCH_STRATEGY stage.

The LLM decides which tool to call and what query to use, observes the
results, and decides whether to continue searching or stop.

State fields produced:
  - raw_results: per-adapter raw hits
  - paper_candidates: unified, deduplicated paper list
  - search_steps: step-by-step log of the React loop
  - trace_events: trace entry
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from ._util import now_iso as _now_iso

logger = logging.getLogger(__name__)

_MAX_STEPS = 8  # max tool calls per search_agent invocation
_MIN_PAPERS = 5  # target minimum papers before stopping
_MIN_REPOS = 1   # target minimum repos before stopping (optional)

# Re3.9: env var disable for S2/OpenAlex (Phase 5 验证用)
_DISABLED_TOOLS: set[str] = set()
if os.environ.get("PAPERAGENT_DISABLE_S2"):
    _DISABLED_TOOLS.add("semantic_scholar")
if os.environ.get("PAPERAGENT_DISABLE_OPENALEX"):
    _DISABLED_TOOLS.add("openalex")


def _get_domain_tools(domain: str) -> set[str]:
    """Return domain-specific tools based on topic domain.

    PubMed is only enabled for medical/biological/chemical topics.
    """
    domain_lower = (domain or "").lower()
    medical_keywords = {"medical", "medicine", "biomedical", "health", "clinical",
                        "bioinformatic", "biological", "lifestream", "medical_ai"}
    if any(kw in domain_lower for kw in medical_keywords):
        return {"pubmed"}
    return set()


class NodeError(RuntimeError):
    pass


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _use_unified() -> bool:
    return os.environ.get("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0") == "1"


def _dedup_key(paper: dict[str, Any]) -> str:
    """Build a dedup key from normalized title + DOI.

    Strips punctuation and collapses whitespace so that minor formatting
    differences across adapters (arXiv vs Crossref) don't cause duplicates.
    """
    doi = (paper.get("doi") or paper.get("DOI") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    title = (paper.get("title") or paper.get("name") or "").strip().lower()
    # Remove all punctuation and collapse whitespace
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return f"title:{title[:80]}" if title else ""


_SYSTEM_PROMPT = """你是学术搜索策略师。根据题目、已有结果和搜索历史，决定下一步搜索什么。

可用工具由 available_sources 字段动态提供；不得使用未在 available_sources 中列出的工具。

判断标准:
- 如果还没有论文 → 搜 method+object 组合
- 如果论文太少 (<5) → 扩大范围或换关键词
- 如果论文够多 (≥5) 但没 repo → 搜 github（仅在 available_sources 中有 github 时）
- 如果论文够多 + 有 repo → 停止
- 如果某个工具在 failed_tools_do_not_retry 列表中 → 不要再用它，换其他工具

重要: source_status=empty 只表示该查询没有命中，不代表 source 失效；
只有 failed、rate_limited、disabled 的 source 不可再选。

输出 JSON:
{"action": "search" | "stop", "tool": "必须来自 available_sources", "query": "...", "reason": "..."}

如果搜索结果已经足够，输出:
{"action": "stop", "reason": "已有 N 篇论文 + M 个 repo，足够开始分析"}

如果所有工具都失败了，输出:
{"action": "stop", "reason": "all tools failed"}

重要: 不要重复已经用过的 tool+query 组合。查看 prior_steps 列表，如果某个查询已经执行过，必须换关键词或换工具。

[OUTPUT CONTRACT] 你必须输出且仅输出一个合法 JSON 对象，不要输出其他内容。"""


def _build_decision_prompt(
    topic: str,
    atoms: dict[str, Any],
    all_papers: list[dict[str, Any]],
    all_repos: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    search_plan: dict[str, Any] | None,
    failed_tools: set[str] | None = None,
) -> str:
    """Build the user prompt for the LLM decision call."""
    method = atoms.get("method") or []
    obj = atoms.get("object") or []
    task = atoms.get("task") or []
    domain = atoms.get("domain") or "unknown"

    # Prior queries already tried
    prior_queries = []
    for s in steps:
        if s.get("type") == "tool_call":
            status = "FAILED" if s.get("failed") else f"{s.get('n_results', 0)} results"
            prior_queries.append(f'{s.get("tool")}: "{s.get("query")}" -> {status}')

    # Available queries from search_plan
    plan_queries = []
    if search_plan and search_plan.get("queries"):
        for q in search_plan["queries"]:
            plan_queries.append(f'{q.get("tool", "?")}: "{q.get("query", "")}"')

    # Failed tools to avoid
    failed_list = sorted(failed_tools) if failed_tools else []

    # Re5.X: inject sources from SourceCatalog instead of hardcoded list
    from apps.api.app.services.search_catalog import get_source_catalog
    catalog = get_source_catalog()
    domain_str = str(domain) if not isinstance(domain, list) else (domain[0] if domain else "unknown")
    allowed_sources = catalog.allowed_source_names(domain_str)
    source_list = catalog.source_list_for_prompt(domain_str)
    domain_tools = _get_domain_tools(domain_str)

    return json.dumps({
        "topic": topic[:200],
        "method_keywords": method[:5],
        "object_keywords": obj[:5],
        "task_keywords": task[:3],
        "domain": domain,
        "available_sources": allowed_sources,
        "source_descriptions": source_list,
        "available_extra_tools": sorted(domain_tools) if domain_tools else [],
        "current_paper_count": len(all_papers),
        "current_repo_count": len(all_repos),
        "prior_steps": prior_queries[-8:] if prior_queries else [],
        "available_plan_queries": plan_queries[:8] if plan_queries else [],
        "failed_tools_do_not_retry": failed_list,
        "step_number": len(steps),
        "max_steps": _MAX_STEPS,
    }, ensure_ascii=False, indent=2)


def _llm_decide(
    topic: str,
    atoms: dict[str, Any],
    all_papers: list[dict[str, Any]],
    all_repos: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    search_plan: dict[str, Any] | None,
    failed_tools: set[str] | None = None,
) -> tuple[dict[str, Any], str]:
    """Call LLM to decide next action.

    Returns a tuple (decision_dict, provider_tag). Provider is one of
    "unified_router", "fast_json", or "local" (fallback).
    """
    user_prompt = _build_decision_prompt(topic, atoms, all_papers, all_repos, steps, search_plan, failed_tools)
    result: dict[str, Any] | None = None
    prov = "fast_json"
    try:
        if _use_unified():
            from apps.api.app.services.router import call_with_contract
            from apps.api.app.services.router.model_policy import TaskRole
            from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
            register_graph_contracts()
            contract_result = call_with_contract(
                user_prompt,
                system=_SYSTEM_PROMPT,
                contract_id="search-decision/v1",
                task_role=TaskRole.search_control,
                max_tokens=500,
                timeout=max(5, _env_int("SEARCH_AGENT_TIMEOUT_S", 20)),
            )
            prov = "unified_router"
            if contract_result.success and isinstance(contract_result.content, dict):
                result = contract_result.content
            else:
                logger.warning("search_agent unified_router failed: %s", contract_result.error)
        else:
            from apps.api.app.services.llm_router import call_json
            result = call_json(
                user_prompt,
                system=_SYSTEM_PROMPT,
                profile="fast_json",
                max_tokens=500,
                expected="dict",
                timeout=max(5, _env_int("SEARCH_AGENT_TIMEOUT_S", 20)),
            )

        if isinstance(result, dict):
            tool = result.get("tool", "").strip().lower()
            query = result.get("query", "").strip()
            used = {
                (s.get("tool"), s.get("query"))
                for s in steps
                if s.get("type") == "tool_call"
            }
            if (tool, query) in used:
                logger.info("search_agent: LLM returned duplicate query %s:%s, using fallback", tool, query[:50])
                fallback = _fallback_decide(steps, search_plan, all_papers, all_repos, failed_tools, atoms)
                if fallback.get("action") != "stop":
                    return fallback, "local"
            return result, prov
    except Exception as exc:
        logger.warning("search_agent LLM decide failed: %s", exc)

    # Fallback: use plan queries in order, then stop
    return _fallback_decide(steps, search_plan, all_papers, all_repos, failed_tools, atoms), "local"


def _count_relevant_papers(papers: list[dict[str, Any]], atoms: dict[str, Any]) -> int:
    """Re3.9.4: Count papers whose titles have keyword overlap with topic_atoms."""
    topic_keywords: set[str] = set()
    for key in ("method", "object", "task", "scenario"):
        for v in (atoms.get(key) or []):
            for word in str(v).lower().split():
                if len(word) >= 3:
                    topic_keywords.add(word)
    if not topic_keywords:
        return len(papers)
    count = 0
    for p in papers:
        title = (p.get("title") or "").lower()
        if any(kw in title for kw in topic_keywords):
            count += 1
    return count


def _final_stop(steps: list, step_idx: int, thought: dict) -> None:
    """Record a stop decision in steps."""
    steps.append({
        "step": step_idx,
        "type": "stop",
        "reason": thought.get("reason", "LLM decided to stop"),
    })


def _generate_reflection_query(
    atoms: dict[str, Any],
    steps: list[dict[str, Any]],
    papers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Re3.9.4: Generate a new search query using reflection strategies."""
    used_queries = {
        (s.get("tool"), s.get("query"))
        for s in steps
        if s.get("type") == "tool_call"
    }
    method = atoms.get("method") or []
    obj = atoms.get("object") or []
    domain = atoms.get("domain") or []

    if obj:
        q = " ".join(obj[:2])
        if ("arxiv", q) not in used_queries:
            return {"tool": "arxiv", "query": q, "strategy": "simplify:object_only"}
    if domain and method:
        q = f"{method[0]} {domain[0]}"
        if ("crossref", q) not in used_queries:
            return {"tool": "crossref", "query": q, "strategy": "broaden:method+domain"}
    if method:
        q = f"{method[0]} application"
        if ("openalex", q) not in used_queries:
            return {"tool": "openalex", "query": q, "strategy": "synonym:method+application"}
    return None


def _fallback_decide(
    steps: list[dict[str, Any]],
    search_plan: dict[str, Any] | None,
    all_papers: list[dict[str, Any]],
    all_repos: list[dict[str, Any]],
    failed_tools: set[str] | None = None,
    atoms: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deterministic fallback when LLM is unavailable: iterate plan queries, then stop."""
    used_queries = {
        (s.get("tool"), s.get("query"))
        for s in steps
        if s.get("type") == "tool_call"
    }
    # Also track skipped tools+queries so we don't keep returning the same skipped query
    skipped_queries = {
        (s.get("tool"), s.get("query"))
        for s in steps
        if s.get("type") == "skip"
    }
    failed = failed_tools or set()

    # Re3.9: if medical domain, try pubmed with method+object keywords as fallback
    if atoms:
        domain_val = atoms.get("domain", "unknown")
        domain_str = str(domain_val[0]) if isinstance(domain_val, list) and domain_val else str(domain_val)
        if _get_domain_tools(domain_str):
            method_kws = atoms.get("method") or []
            obj_kws = atoms.get("object") or []
            pubmed_q = " ".join((method_kws + obj_kws)[:3])
            if pubmed_q and ("pubmed", pubmed_q) not in used_queries and "pubmed" not in failed:
                return {"action": "search", "tool": "pubmed", "query": pubmed_q,
                        "reason": "domain fallback: medical topic, pubmed search"}

    if search_plan and search_plan.get("queries"):
        for q in search_plan["queries"]:
            tool = q.get("tool", "")
            query = q.get("query", "")
            # Skip if already used, already skipped, tool failed, or empty query
            if (tool, query) in used_queries or (tool, query) in skipped_queries:
                continue
            if tool in failed:
                continue
            if query:
                return {"action": "search", "tool": tool, "query": query, "reason": "plan fallback"}

    # If we have enough papers, stop
    if len(all_papers) >= _MIN_PAPERS:
        return {"action": "stop", "reason": f"fallback: {len(all_papers)} papers collected"}

    # If no plan queries left but we have some papers, stop
    if all_papers:
        return {"action": "stop", "reason": f"fallback: {len(all_papers)} papers, plan exhausted"}

    return {"action": "stop", "reason": "fallback: no plan queries available"}


async def _run_tool(tool: str, query: str, top_k: int = 12) -> list[dict[str, Any]]:
    """Call a retrieval adapter by name.

    Re5.X: empty results are NOT failures — they're query misses.
    Only exceptions set failed_this_round.
    """
    from apps.api.app.services.search_catalog import get_source_catalog
    catalog = get_source_catalog()
    # Re5.X: check SourcePolicy (replaces old _DISABLED_TOOLS env vars)
    if not catalog.is_available(tool):
        logger.info("search_agent: tool %s not available (disabled or not in catalog)", tool)
        return []
    from apps.api.app.services.retrieval.adapters import REGISTRY
    if tool not in REGISTRY:
        logger.warning("search_agent: tool %s not in REGISTRY", tool)
        return []
    try:
        results = await REGISTRY[tool]([query], top_k)
        return results  # empty list = query miss, NOT failure
    except Exception as exc:
        logger.warning("search_agent: tool %s failed: %s", tool, type(exc).__name__)
        raise  # let caller handle — distinguishes failure from empty


def _run_tool_sync(tool: str, query: str, top_k: int = 12) -> list[dict[str, Any]]:
    """Synchronous wrapper for _run_tool, safe in threads with existing event loops.

    Uses asyncio.new_event_loop() instead of asyncio.run() to avoid crashes
    when an event loop is already running in the current thread (e.g. inside
    LangGraph's async streaming context).
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside a running loop — use a fresh loop in this thread.
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(_run_tool(tool, query, top_k))
            finally:
                new_loop.close()
        else:
            return loop.run_until_complete(_run_tool(tool, query, top_k))
    except RuntimeError:
        # No event loop at all — create one.
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(_run_tool(tool, query, top_k))
        finally:
            new_loop.close()


def _classify_results(tool: str, results: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """Split results into papers and repos."""
    papers = []
    repos = []
    for h in results:
        title = (h.get("title") or h.get("full_name") or h.get("name") or "").strip()
        if not title and tool == "github":
            url = h.get("url") or h.get("html_url") or ""
            if url:
                parts = url.rstrip("/").split("/")
                if len(parts) >= 2:
                    title = f"{parts[-2]}/{parts[-1]}"
                elif parts:
                    title = parts[-1]
        if not title or len(title) < 3:
            continue

        abstract = (h.get("abstract") or h.get("description") or h.get("full_text") or "")[:600]
        url = h.get("url") or h.get("html_url") or h.get("abs_url") or ""

        if tool == "github" and "api.github.com/repos/" in url:
            path = url.split("api.github.com/repos/", 1)[-1].rstrip("/")
            url = f"https://github.com/{path}"

        entry = {
            "title": title,
            "abstract": abstract,
            "url": url,
            "doi": h.get("doi") or h.get("DOI"),
            "arxiv_id": h.get("arxiv_id"),
            "source": tool,
            "hits": {tool: [h]},
        }
        # Propagate _crossref_type for quality_filter component filtering
        if h.get("_crossref_type"):
            entry["_crossref_type"] = h["_crossref_type"]
        if tool == "github":
            repos.append(entry)
        else:
            papers.append(entry)
    return papers, repos


def search_agent_node(state: ResearchState) -> dict[str, Any]:
    """React loop: think → call → observe → decide."""
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    search_plan = state.get("search_plan") or {}
    t0 = time.time()

    trace: dict[str, Any] = {
        "node": "search_agent",
        "started_at": _now_iso(),
        "input_summary": {
            "topic_len": len(topic),
            "has_atoms": bool(atoms),
            "has_plan": bool(search_plan.get("queries")),
            "provider": "react_search",
        },
        "output_summary": {},
        "tool_calls": [],
        "errors": [],
        "provider": "react_search",
        "state_keys": ["raw_results", "paper_candidates", "repo_candidates",
                        "search_steps", "trace_events", "errors",
                        "provider_profile"],
    }
    decision_provider = "react_search"
    errors: list[dict[str, Any]] = []

    # Repair round detection (skip failed adapters)
    repair_rounds = state.get("evidence_audit", {}).get("repair_rounds", 0)
    skip_adapters: set[str] = set()
    if repair_rounds > 0:
        prior_traces = state.get("trace_events") or []
        retrieve_traces = [
            t for t in prior_traces
            if t.get("node") in ("retrieve", "paper_retriever", "search_agent")
        ]
        if retrieve_traces:
            last_failed = retrieve_traces[-1].get("output_summary", {}).get("failed_adapters", [])
            skip_adapters = set(last_failed or [])
            if skip_adapters:
                logger.info("repair round: skipping adapters: %s", skip_adapters)

    all_papers: list[dict[str, Any]] = []
    all_repos: list[dict[str, Any]] = []
    raw: dict[str, list[dict[str, Any]]] = {}
    steps: list[dict[str, Any]] = []
    failed_this_round: set[str] = set()  # tools that failed within this invocation

    try:
        # Re3.9.1: Resolve domain-specific tools for injection
        domain_str = str(atoms.get("domain", "unknown"))
        if isinstance(atoms.get("domain"), list) and atoms["domain"]:
            domain_str = str(atoms["domain"][0])
        domain_tools = _get_domain_tools(domain_str)

        for step_idx in range(_MAX_STEPS):
            # 1. Think: LLM decides next action
            thought, prov = _llm_decide(topic, atoms, all_papers, all_repos, steps, search_plan, failed_this_round)
            if decision_provider == "react_search":
                decision_provider = prov

            # Re3.9.1: If LLM wants to stop but domain tool (e.g. pubmed) not yet tried,
            # inject it before stopping — but only if we still have steps left
            if thought.get("action") == "stop" and domain_tools:
                used_tools = {s.get("tool") for s in steps if s.get("type") == "tool_call"}
                unused_domain = domain_tools - used_tools - failed_this_round - skip_adapters
                if unused_domain and step_idx < _MAX_STEPS - 1:
                    inject_tool = sorted(unused_domain)[0]
                    method_kws = atoms.get("method") or []
                    obj_kws = atoms.get("object") or []
                    inject_query = " ".join((method_kws + obj_kws)[:3])
                    if inject_query:
                        logger.info("search_agent: injecting domain tool %s before stop (domain=%s)",
                                    inject_tool, domain_str)
                        thought = {
                            "action": "search",
                            "tool": inject_tool,
                            "query": inject_query,
                            "reason": f"domain injection before stop: {domain_str} topic",
                        }

            # Re3.9.1: If LLM didn't stop, and domain tool not yet used, inject at step >= 2
            if thought.get("action") != "stop" and domain_tools and len(steps) >= 2:
                used_tools = {s.get("tool") for s in steps if s.get("type") == "tool_call"}
                unused_domain = domain_tools - used_tools - failed_this_round - skip_adapters
                if unused_domain:
                    inject_tool = sorted(unused_domain)[0]
                    method_kws = atoms.get("method") or []
                    obj_kws = atoms.get("object") or []
                    inject_query = " ".join((method_kws + obj_kws)[:3])
                    if inject_query:
                        logger.info("search_agent: injecting domain tool %s for %s domain",
                                    inject_tool, domain_str)
                        thought = {
                            "action": "search",
                            "tool": inject_tool,
                            "query": inject_query,
                            "reason": f"domain injection: {domain_str} topic, forced {inject_tool}",
                        }

            if thought.get("action") == "stop":
                # R6.7: when LLM stops with 0 papers, try unused plan queries before giving up
                if not all_papers and search_plan and search_plan.get("queries"):
                    used = {(s.get("tool"), s.get("query")) for s in steps if s.get("type") == "tool_call"}
                    remaining = [q for q in search_plan["queries"]
                                 if (q.get("tool"), q.get("query")) not in used]
                    if remaining and step_idx < _MAX_STEPS - 1:
                        next_q = remaining[0]
                        logger.info("search_agent: overruling stop, %d queries remaining, forcing %s",
                                     len(remaining), next_q.get("tool"))
                        thought = {"action": "search", "tool": next_q.get("tool", ""),
                                    "query": next_q.get("query", ""),
                                    "reason": "forced: unused plan query"}
                        # fall through to execution below
                    else:
                        _final_stop(steps, step_idx, thought)
                        break
                else:
                    # Re3.9.4: Relevance-aware stop
                    _atoms_for_rel = state.get("topic_atoms") or {}
                    if _atoms_for_rel and all_papers and step_idx < _MAX_STEPS - 2:
                        _rel_count = _count_relevant_papers(all_papers, _atoms_for_rel)
                        _total = len(all_papers)
                        _ratio = _rel_count / _total if _total > 0 else 1.0
                        if _ratio < 0.3 and _total < 15:
                            _reflection = _generate_reflection_query(_atoms_for_rel, steps, all_papers)
                            if _reflection:
                                logger.info("search_agent: stop blocked, relevance=%d/%d=%.0f%%, reflecting",
                                             _rel_count, _total, _ratio * 100)
                                _final_stop(steps, step_idx, thought)
                                thought = {
                                    "action": "search",
                                    "tool": _reflection.get("tool", "arxiv"),
                                    "query": _reflection.get("query", ""),
                                    "reason": f"reflection: low relevance ({_ratio:.0%})",
                                }
                            else:
                                _final_stop(steps, step_idx, thought)
                                break
                        else:
                            _final_stop(steps, step_idx, thought)
                            break
                    else:
                        _final_stop(steps, step_idx, thought)
                        break

            tool = thought.get("tool", "").strip().lower()
            query = thought.get("query", "").strip()

            if not tool or not query:
                steps.append({
                    "step": step_idx,
                    "type": "stop",
                    "reason": "empty tool or query from LLM",
                })
                break

            # Skip tools that failed in prior repair round OR this invocation
            if tool in skip_adapters or tool in failed_this_round:
                steps.append({
                    "step": step_idx,
                    "type": "skip",
                    "tool": tool,
                    "query": query,
                    "reason": f"adapter {tool} skipped (failed)",
                })
                continue

            # 2. Call tool
            try:
                results = _run_tool_sync(tool, query, 12)
            except Exception:
                # Re5.X: actual failure (not empty) → mark as failed
                failed_this_round.add(tool)
                steps.append({
                    "step": step_idx,
                    "type": "tool_call",
                    "tool": tool,
                    "query": query,
                    "n_results": 0,
                    "n_papers": 0,
                    "n_repos": 0,
                    "reason": thought.get("reason", ""),
                    "failed": True,
                })
                continue

            # Re5.X: empty results are NOT failures — they're query misses
            # Do NOT add to failed_this_round

            # 3. Observe
            new_papers, new_repos = _classify_results(tool, results)
            all_papers.extend(new_papers)
            all_repos.extend(new_repos)
            raw.setdefault(tool, []).extend(results)

            n_results = len(results)
            steps.append({
                "step": step_idx,
                "type": "tool_call",
                "tool": tool,
                "query": query,
                "n_results": n_results,
                "n_papers": len(new_papers),
                "n_repos": len(new_repos),
                "reason": thought.get("reason", ""),
                "failed": n_results == 0,
            })

            # If all available tools have failed, stop early
            available_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                               "huggingface", "core", "datacite"} | domain_tools
            remaining = available_tools - skip_adapters - failed_this_round
            if not remaining and not all_papers:
                steps.append({
                    "step": step_idx,
                    "type": "stop",
                    "reason": "all available tools failed",
                })
                break

            # Re3.9.3: incremental dedup + partial state write for real-time streaming
            _seen_keys: set[str] = set()
            _unique_papers: list[dict[str, Any]] = []
            for p in all_papers:
                key = _dedup_key(p)
                if key and key not in _seen_keys:
                    _seen_keys.add(key)
                    _unique_papers.append(p)
            _seen_repo_keys: set[str] = set()
            _unique_repos: list[dict[str, Any]] = []
            for r in all_repos:
                key = _dedup_key(r)
                if key and key not in _seen_repo_keys:
                    _seen_repo_keys.add(key)
                    _unique_repos.append(r)

            case_id_for_partial = state.get("case_id", "")
            if case_id_for_partial:
                import pathlib as _pl
                _partial_path = _pl.Path("tmp_re13_eval") / case_id_for_partial / "state_partial.json"
                _partial_path.parent.mkdir(parents=True, exist_ok=True)
                _partial = {
                    "paper_candidates": _unique_papers,
                    "repo_candidates": _unique_repos,
                    "search_steps": steps,
                    "last_update": _now_iso(),
                }
                _partial_path.write_text(
                    json.dumps(_partial, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )

        # Deduplicate papers — normalized title + DOI key
        seen_keys: set[str] = set()
        unique_papers: list[dict[str, Any]] = []
        for p in all_papers:
            key = _dedup_key(p)
            if key and key not in seen_keys:
                seen_keys.add(key)
                unique_papers.append(p)

        # Deduplicate repos
        seen_repo_keys: set[str] = set()
        unique_repos: list[dict[str, Any]] = []
        for r in all_repos:
            key = _dedup_key(r)
            if key and key not in seen_repo_keys:
                seen_repo_keys.add(key)
                unique_repos.append(r)

        all_tool_order = [tool for tool in ("arxiv", "openalex", "crossref", "github", "semantic_scholar", "huggingface", "core", "datacite", "pubmed") if tool in raw]
        failed_adapters = sorted(skip_adapters | failed_this_round)
        per_adapter = {tool: len(raw.get(tool, [])) for tool in all_tool_order}

        trace["output_summary"] = {
            "n_paper_candidates": len(unique_papers),
            "n_repo_candidates": len(unique_repos),
            "n_steps": len(steps),
            "n_tool_calls": sum(1 for s in steps if s.get("type") == "tool_call"),
            "raw_tools": list(raw.keys()),
            "per_adapter": per_adapter,
            "failed_adapters": failed_adapters,
            "skipped_adapters": list(skip_adapters),
            "repair_rounds": repair_rounds,
        }
        trace["provider"] = decision_provider
        trace["input_summary"]["provider"] = decision_provider
        trace["tool_calls"] = [
            {"tool": "search-decision/v1" if decision_provider == "unified_router" else "llm_decide",
             "mode": decision_provider},
        ] + [
            {"tool": k, "n": len(v)} for k, v in raw.items()
        ]

        # Re3.0 fix: do NOT mix repos into paper_candidates — they go to repo_candidates only.
        # Previously repos were appended to paper_candidates, causing GitHub entries to appear
        # in verified_papers after quality_filter (which passes github as True).
        paper_candidates = unique_papers

    except NodeError as exc:
        logger.warning("search_agent_node failed: %s", exc)
        errors.append({"node": "search_agent", "error": f"search_failed:{exc}"})
        trace["errors"].append({"phase": "search_agent", "error": str(exc)})
        paper_candidates = []
        unique_repos = []
    except Exception as exc:
        logger.exception("search_agent_node unexpected error")
        errors.append({"node": "search_agent", "error": type(exc).__name__})
        trace["errors"].append({"phase": "search_agent", "error": type(exc).__name__})
        paper_candidates = []
        unique_repos = []

    trace["ended_at"] = _now_iso()
    trace["elapsed_s"] = round(time.time() - t0, 3)

    return {
        "raw_results": raw,
        "paper_candidates": paper_candidates,
        "repo_candidates": unique_repos,
        "search_steps": steps,
        "trace_events": [trace],
        "errors": errors,
        "provider_profile": decision_provider,
    }
