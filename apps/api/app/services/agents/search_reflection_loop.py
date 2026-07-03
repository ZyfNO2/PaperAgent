"""Re10 SearchReflectionLoop — SOP §3.1 + §5 + §7.

Top-level orchestrator that runs up to ``max_rounds`` (default 3) of:

  DomainScout → Plan queries → SearchExecutor → ObservationBuilder
    → ReflectionCritic → URLRepair / QueryRepair / drop
    → CandidateVerifier → EvidenceMerger → StopController

The loop MUST:
  * preserve seed_candidates (Re08/Re09) — never rebuild the pool
    from zero (SOP §3.1 + Re09 retrospective).
  * call URLRepairAgent on every empty-URL candidate before
    classification (SOP §6.1).
  * call QueryRepairAgent on every ``{X}``/``X`` query before any
    adapter call (SOP §4.4).
  * tag every candidate with ``source_run = re08 | re09 | re10_round_n``
    (SOP §9.5).
  * dedupe by normalized title / DOI / arxiv_id.

ponytail:
- Plan/observation shapes are split into ``search_reflection_helpers``
  to keep this file under the 350-line mark.
- Closure captures ``retrieval_clients`` + ``llm_client`` once.
- LLM-free path: DomainScout / ReflectionCritic / QueryRepair all
  have rule-layer fallbacks.  The loop runs without LLM if needed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from .candidate_verifier import verify_candidate_offline
from .domain_scout_agent import run_domain_scout
from .query_repair_agent import repair_query
from .reflection_critic_agent import run_reflection_critic
from .search_reflection_helpers import (
    bucket_for_tool,
    build_observations,
    build_round_plan,
    candidate_key,
    ensure_source_run,
    has_placeholder,
)
from .trace_ledger import TraceLedger
from .url_repair_agent import repair_candidate_url

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools registry (SOP §2.2 + Re09).
# ---------------------------------------------------------------------------

DEFAULT_TOOLS: tuple[str, ...] = ("arxiv", "openalex", "crossref", "github", "huggingface")

TOOL_CLIENT_KEYS: dict[str, str] = {
    "arxiv": "arxiv_search",
    "openalex": "openalex_search",
    "crossref": "crossref_search",
    "github": "github_search",
    "huggingface": "huggingface_search",
}


# ---------------------------------------------------------------------------
# Adapter dispatch + URL repair pipeline
# ---------------------------------------------------------------------------


async def _execute_query(
    tool: str, query: str, retrieval_clients: dict, top_k: int = 3,
) -> tuple[list[dict], dict]:
    client_key = TOOL_CLIENT_KEYS.get(tool, tool)
    fn = retrieval_clients.get(client_key) if retrieval_clients else None
    if fn is None:
        return [], {
            "type": "search", "tool": tool, "query": query,
            "status": "error", "result_count": 0, "error": f"missing client {client_key}",
        }
    started = time.monotonic()
    try:
        # Adapters accept (query: str, top_k: int) but historically some
        # accept a list. Try str first, fall back to list — ponytail:
        # one-line adaptation for legacy wrappers.
        try:
            hits = await fn(query, top_k=top_k)
        except TypeError:
            hits = await fn([query], top_k=top_k)
    except Exception as exc:
        return [], {
            "type": "search", "tool": tool, "query": query,
            "status": "error", "result_count": 0, "error": repr(exc),
        }
    return list(hits or []), {
        "type": "search", "tool": tool, "query": query,
        "status": "success" if hits else "no_results",
        "result_count": len(hits or []),
        "duration_sec": round(time.monotonic() - started, 3),
        "candidate_ids": [
            str(h.get("url") or h.get("title") or idx)
            for idx, h in enumerate(hits or [])
        ][:5],
        "error": "",
    }


async def _process_hit(
    hit: dict, tool: str, retrieval_clients: dict, topic_atoms: dict,
    actions: list[dict], seen_keys: set[str], seen_local: set[str],
) -> tuple[dict | None, bool]:
    """URL-repair + verify a single hit. Returns (cand_or_None, is_accepted)."""
    if not isinstance(hit, dict):
        return None, False
    key = candidate_key(hit)
    if key in seen_keys or key in seen_local:
        return None, False
    seen_local.add(key)
    cand = dict(hit)
    cand["_bucket"] = bucket_for_tool(tool, hit)
    url_repaired = False
    if not (cand.get("url") or cand.get("arxiv_id") or cand.get("doi")):
        try:
            ur = await repair_candidate_url(cand, retrieval_clients=retrieval_clients)
        except Exception as exc:
            ur = {
                "url_status": "candidate_unverified",
                "url": "",
                "evidence": f"URL repair raised: {exc!r}",
            }
        cand["url_status"] = ur.get("url_status")
        if ur.get("url"):
            cand["url"] = ur["url"]
            url_repaired = True
        actions.append({
            "type": "repair_url", "tool": "url_repair",
            "query": (cand.get("title") or "")[:60],
            "status": ur.get("url_status"),
            "result_count": 1 if ur.get("url") else 0,
            "error": ur.get("evidence") or "",
        })
    try:
        verdict = verify_candidate_offline(cand, topic_atoms, role=cand["_bucket"])
    except Exception as exc:
        verdict = None
        logger.warning("verify_candidate_offline raised: %s", exc)
    if verdict is not None:
        cand["verification_status"] = verdict.verification_status
        cand["verification_topic_relation"] = verdict.topic_relation
        accepted = verdict.verification_status in {"verified", "metadata_repaired"}
    else:
        cand["verification_status"] = "unverified"
        accepted = True
    return cand, accepted


# ---------------------------------------------------------------------------
# One round
# ---------------------------------------------------------------------------


async def _run_one_round(
    *,
    round_num: int,
    topic: str,
    topic_atoms: dict,
    base_seed_pool: dict,
    history: dict,
    domain_kws: dict,
    must_search: list[str],
    llm_client,
    retrieval_clients: dict,
    trace: TraceLedger,
) -> dict:
    plan = build_round_plan(domain_kws, history, must_search)
    if not plan:
        plan = [{
            "query": topic, "tool": "arxiv", "target_role": "core_paper",
            "why": "fallback: search raw topic", "expected_signal": "title",
        }]

    accepted: list[dict] = []
    rejected: list[dict] = []
    placeholder_leaks: list[str] = []
    failed_queries: list[dict] = []
    actions: list[dict] = []
    url_repair_n = 0
    query_repair_n = 0
    tool_error_n = 0
    missing_client_n = 0
    successful_action_n = 0
    seen_keys: set[str] = set(base_seed_pool.keys())

    for entry in plan:
        q = entry.get("query") or ""
        tool = entry.get("tool") or "arxiv"
        if has_placeholder(q):
            placeholder_leaks.append(q)
            repair = repair_query(q, topic_atoms, domain_kws)
            query_repair_n += 1
            actions.append({
                "type": "repair_query", "tool": tool, "query": q,
                "status": repair.get("status"),
                "result_count": len(repair.get("repaired_queries") or []),
                "error": repair.get("reason") or "",
            })
            if repair.get("status") != "repaired" or not repair.get("repaired_queries"):
                failed_queries.append({
                    "query": q, "tool": tool,
                    "error": f"query_repair: {repair.get('status')} ({repair.get('reason')})",
                })
                continue
            q = repair["repaired_queries"][0]

        hits, action = await _execute_query(tool, q, retrieval_clients, top_k=3)
        actions.append(action)
        if action.get("status") == "error":
            tool_error_n += 1
            err_msg = str(action.get("error") or "")
            if "missing client" in err_msg:
                missing_client_n += 1
        elif action.get("status") in ("success", "no_results"):
            successful_action_n += 1
        if action.get("status") in ("error", "no_results"):
            failed_queries.append({
                "query": q, "tool": tool, "error": action.get("error") or action.get("status"),
            })

        seen_local: set[str] = set()
        for hit in hits:
            cand, ok = await _process_hit(
                hit, tool, retrieval_clients, topic_atoms, actions, seen_keys, seen_local,
            )
            if cand is None:
                continue
            seen_keys.add(candidate_key(cand))
            if cand.get("url_status") in {"url_repaired"} or cand.get("url"):
                url_repair_n += 1
            if ok:
                accepted.append(cand)
            else:
                rejected.append(cand)

    observations = build_observations(
        plan, [], accepted, rejected, placeholder_leaks,
        failed_queries, url_repair_n, round_num,
    )
    observations["tool_stats"] = {
        "tool_error_n": tool_error_n,
        "missing_client_n": missing_client_n,
        "successful_action_n": successful_action_n,
    }
    reflection = await run_reflection_critic(
        topic, topic_atoms, observations, llm_client=llm_client,
    )

    trace.record_round(
        case_id=trace.case_id,
        round_num=round_num,
        agent="SearchReflectionLoop",
        input_summary={
            "must_search_n": len(must_search),
            "avoid_search_n": len(history.get("avoid_search") or []),
            "seed_pool_n": len(base_seed_pool),
        },
        actions=actions,
        observations=observations,
        reflection=reflection,
        new_candidates_n=len(accepted),
        accepted_n=len(accepted),
        rejected_n=len(rejected),
        url_repair_n=url_repair_n,
        query_repair_n=query_repair_n,
    )

    return {
        "round": round_num,
        "accepted": accepted,
        "rejected": rejected,
        "actions": actions,
        "observations": observations,
        "reflection": reflection,
        "plan": plan,
        "url_repair_n": url_repair_n,
        "query_repair_n": query_repair_n,
        "tool_stats": observations["tool_stats"],
    }


# ---------------------------------------------------------------------------
# Stop controller (SOP §7)
# ---------------------------------------------------------------------------


def _decide_stop(rounds: list[dict], all_accepted: list[dict], max_rounds: int) -> str:
    if not rounds:
        return "blocked"
    papers = [c for c in all_accepted if c.get("_bucket") in (None, "paper")]
    baseline = [c for c in all_accepted if "baseline" in (c.get("role") or "")]
    datasets = [c for c in all_accepted if c.get("_bucket") == "dataset"]
    repos = [c for c in all_accepted if c.get("_bucket") == "repo"]
    if (
        len(papers) >= 4
        and (len(baseline) >= 1 or len(papers) >= 5)
        and len(datasets) >= 1
        and len(repos) >= 1
    ):
        return "sufficient_evidence"
    if len(rounds) >= max_rounds:
        return "max_rounds"
    # Tooling failure takes precedence: if current OR last round had any tool
    # errors AND no actions succeeded, the reflection isn't a "no new signal"
    # verdict — it's the loop unable to talk to adapters.
    cur = rounds[-1] if rounds else {}
    cur_stats = cur.get("tool_stats") or {}
    cur_has_error_no_success = (
        cur_stats.get("tool_error_n", 0) > 0
        and cur_stats.get("successful_action_n", 0) == 0
    )
    prev_has_error_no_success = False
    if len(rounds) >= 2:
        prev = rounds[-2]
        prev_stats = prev.get("tool_stats") or {}
        prev_has_error_no_success = (
            prev_stats.get("tool_error_n", 0) > 0
            and prev_stats.get("successful_action_n", 0) == 0
        )
    if cur_has_error_no_success or prev_has_error_no_success:
        return "blocked_tooling"
    if len(rounds) >= 2:
        last_two = rounds[-2:]
        if all(r.get("accepted_n", len(r.get("accepted") or [])) < 2 for r in last_two):
            # Only return no_new_signal if at least one action in either round
            # was non-error (success or no_results). Otherwise surface as
            # blocked_tooling — the loop couldn't actually exercise the search
            # space.
            has_real_signal = any(
                (r.get("tool_stats") or {}).get("successful_action_n", 0) > 0
                for r in last_two
            )
            if has_real_signal:
                return "no_new_signal"
            return "blocked_tooling"
    return ""


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


async def run_search_reflection_loop(
    topic: str,
    *,
    topic_atoms: dict,
    seed_candidates: list[dict] | None = None,
    out_dir: str,
    case_id: str | None = None,
    max_rounds: int = 3,
    llm_client=None,
    retrieval_clients: dict,
) -> dict:
    """Run the multi-loop reflection search (SOP §3.1)."""
    seed_candidates = seed_candidates or []
    if not case_id:
        case_id = f"re10_{abs(hash(topic)) % (10**6):06d}_{int(time.time())}"

    seed_pool: dict[str, dict] = {}
    for c in seed_candidates:
        if not isinstance(c, dict):
            continue
        key = candidate_key(c)
        if key in seed_pool:
            continue
        seed_pool[key] = ensure_source_run(c, c.get("source_run") or "re08")

    seed_sources = {
        "re08_candidates_n": sum(1 for c in seed_pool.values() if c.get("source_run") == "re08"),
        "re09_candidates_n": sum(1 for c in seed_pool.values() if c.get("source_run") == "re09"),
    }

    trace = TraceLedger(
        out_dir=out_dir,
        case_id=case_id,
        topic=topic,
        seed_sources=seed_sources,
        max_rounds=max_rounds,
    )

    history: dict = {
        "previous_success": [], "previous_noise": [],
        "previous_failed_queries": [], "avoid_search": [],
    }
    domain_kws: dict = {}
    all_accepted: list[dict] = list(seed_pool.values())
    rounds: list[dict] = []
    stop_reason = "blocked"

    for round_num in range(1, max_rounds + 1):
        if round_num == 1 or not domain_kws:
            scout = await run_domain_scout(
                topic, topic_atoms,
                llm_client=llm_client, history=history,
            )
            domain_kws = scout.get("domain_keywords") or {}
            must_search = scout.get("must_search") or []
            history["avoid_search"] = list(set(
                (history.get("avoid_search") or []) + (scout.get("avoid_search") or [])
            ))
        else:
            focus = (rounds[-1].get("reflection") or {}).get("next_round_focus") or []
            must_search = []
            for f in focus[:4]:
                low = f.lower()
                if "dataset" in low:
                    must_search.append(f"{topic} dataset benchmark")
                elif "repo" in low or "github" in low:
                    must_search.append(f"{topic} github implementation")
                elif "baseline" in low:
                    must_search.append(f"{topic} baseline method")
                else:
                    head = f.split()[0] if f.split() else ""
                    must_search.append(f"{topic} {head}".strip())

        round_summary = await _run_one_round(
            round_num=round_num,
            topic=topic,
            topic_atoms=topic_atoms,
            base_seed_pool=seed_pool,
            history=history,
            domain_kws=domain_kws,
            must_search=must_search,
            llm_client=llm_client,
            retrieval_clients=retrieval_clients,
            trace=trace,
        )

        for c in round_summary.get("accepted", []):
            c2 = ensure_source_run(c, f"re10_round_{round_num}")
            key = candidate_key(c2)
            if key not in seed_pool:
                seed_pool[key] = c2
                all_accepted.append(c2)
        history["previous_success"] = [
            c.get("title") for c in round_summary.get("accepted", []) if c.get("title")
        ][:10]
        history["previous_noise"] = [
            c.get("title") for c in round_summary.get("rejected", []) if c.get("title")
        ][:10]
        history["previous_failed_queries"] = round_summary["observations"].get("failed_queries") or []
        rounds.append({
            "round": round_num,
            "agent": "SearchReflectionLoop",
            "actions": round_summary.get("actions", []),
            "accepted_n": len(round_summary.get("accepted", [])),
            "rejected_n": len(round_summary.get("rejected", [])),
            "url_repair_n": round_summary.get("url_repair_n", 0),
            "query_repair_n": round_summary.get("query_repair_n", 0),
            "tool_stats": round_summary.get("tool_stats", {}),
            "reflection": round_summary.get("reflection", {}),
            "observations": round_summary.get("observations", {}),
        })

        stop = _decide_stop(rounds, all_accepted, max_rounds)
        if stop:
            stop_reason = stop
            break

    paper_n = sum(1 for c in all_accepted if c.get("_bucket") in (None, "paper"))
    baseline_n = sum(1 for c in all_accepted if "baseline" in (c.get("role") or ""))
    parallel_n = sum(1 for c in all_accepted if "parallel" in (c.get("role") or ""))
    dataset_n = sum(1 for c in all_accepted if c.get("_bucket") == "dataset")
    repo_n = sum(1 for c in all_accepted if c.get("_bucket") == "repo")

    remaining: list[str] = []
    if dataset_n == 0:
        remaining.append("dataset_gap")
    if repo_n == 0:
        remaining.append("repo_gap")
    if baseline_n == 0:
        remaining.append("baseline_gap")
    if paper_n < 4:
        remaining.append("paper_shortage")

    trace.finalize(
        case_id=case_id,
        stop_reason=stop_reason,
        paper_n=paper_n,
        baseline_n=baseline_n,
        parallel_n=parallel_n,
        dataset_n=dataset_n,
        repo_n=repo_n,
        remaining_gaps=remaining,
    )

    return {
        "topic": topic,
        "final_candidate_pool": list(seed_pool.values()),
        "rounds": rounds,
        "trace_path": str(trace.trace_path),
        "stop_reason": stop_reason,
        "summary": {
            "paper_n": paper_n,
            "baseline_n": baseline_n,
            "parallel_n": parallel_n,
            "dataset_n": dataset_n,
            "repo_n": repo_n,
            "remaining_gaps": remaining,
        },
    }


# ponytail: tiny self-check.
if __name__ == "__main__":  # pragma: no cover
    import tempfile

    async def _demo() -> None:
        with tempfile.TemporaryDirectory() as td:
            out = await run_search_reflection_loop(
                "Underwater acoustic target recognition",
                topic_atoms={
                    "task": [{"en": "underwater acoustic recognition"}],
                    "object": [{"en": "ship-radiated noise"}],
                },
                seed_candidates=[
                    {"title": "Re08 Seed Paper", "url": "https://example.com/p1",
                     "source_run": "re08", "_bucket": "paper"},
                ],
                out_dir=td,
                max_rounds=2,
                llm_client=None,
                retrieval_clients={},
            )
            print(json.dumps(out.get("summary", {}), ensure_ascii=False, indent=2))
            print("trace:", out.get("trace_path"))
            print("stop:", out.get("stop_reason"))

    asyncio.run(_demo())
