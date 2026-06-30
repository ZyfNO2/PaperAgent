"""Session 63 T5: Research planner agent orchestration.

Pipeline: parse → decompose → strategy → collect → screen → direction advice.
LLM 失败时全部走启发式 fallback, 不让服务挂掉.

Ladder rationale (ponytail):
- 复用 chat_json + 已有 prompts/parser/router, 不另造 abstraction.
- 每个 step 函数最小 diff, 共享同一 trace project_id.
- 单 __main__ self-check, 无测试框架.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from .research_prompts import (
    candidate_screen_system,
    candidate_screen_user,
    direction_advice_system,
    direction_advice_user,
    problem_decompose_system,
    problem_decompose_user,
    search_strategy_system,
    search_strategy_user,
    topic_understand_system,
    topic_understand_user,
)
from .research_topic_parser import parse_topic_rule_based, validate_and_repair_llm_output
from .research_tool_router import (
    search_datasets,
    search_papers,
    search_repos,
    trace_write_event,
)
from .llm import LLMUnavailable, chat_json


# ponytail: research_query_builder (T3) is in progress — use heuristic via
# research_query_expander.expand_topic if builder module is absent.
try:
    from .research_query_builder import ensure_minimum_queries  # type: ignore[import-not-found]
    _HAS_QUERY_BUILDER = True
except ImportError:
    _HAS_QUERY_BUILDER = False


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM call helper — returns dict, falls back to {} on failure
# ---------------------------------------------------------------------------

def _llm_or_empty(prompt: str, system: str) -> dict:
    """Call LLM, return parsed dict. Empty dict on LLM failure.

    Caller decides what to do with empty — typically falls through to
    rule-based parse / heuristic expansion.
    """
    try:
        result = chat_json(prompt, system=system, temperature=0.2, max_tokens=1500)
        if isinstance(result, dict):
            return result
        return {}
    except LLMUnavailable as exc:
        logger.warning("LLM unavailable: %s — falling back to heuristic", exc)
        return {}
    except Exception as exc:
        logger.warning("LLM call failed: %s — falling back to heuristic", exc)
        return {}


def _gen_project_id() -> str:
    """Stable project_id per orchestration run — threads through all trace events."""
    return f"respln-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Step 1: topic_understand
# ---------------------------------------------------------------------------

def topic_understand(
    raw_topic: str,
    student_context: dict | None = None,
    project_id: str = "",
) -> dict:
    """LLM-driven topic parse with rule-based fallback.

    Returns a dict matching the topic_understand schema (validated/repaired).
    """
    project_id = project_id or _gen_project_id()
    trace_write_event(
        "topic_parse_started",
        {"raw_topic": raw_topic, "phase": "research_planner"},
        project_id=project_id,
    )

    student_ctx = student_context or {}
    student_str = (
        f"专业: {student_ctx.get('major', '未指定')}; "
        f"年级: {student_ctx.get('year', '未指定')}; "
        f"工具: {student_ctx.get('tools_known', '未指定')}"
    )
    local_hints = student_ctx.get("local_case_hints", "")

    prompt = topic_understand_user(raw_topic, student_str, local_hints)
    llm_out = _llm_or_empty(prompt, topic_understand_system())

    if llm_out:
        parsed = validate_and_repair_llm_output(llm_out, raw_topic)
    else:
        parsed = parse_topic_rule_based(raw_topic)
        parsed["llm_output_repaired"] = False
        parsed["domain_route_conflict"] = False

    trace_write_event(
        "topic_parse_completed",
        {
            "raw_topic": raw_topic,
            "domain_route": parsed.get("domain_route", "unknown"),
            "needs_clarification_count": len(parsed.get("needs_clarification", [])),
        },
        project_id=project_id,
    )

    parsed["_project_id"] = project_id
    return parsed


# ---------------------------------------------------------------------------
# Step 2: ask_human_confirmation
# ---------------------------------------------------------------------------

def ask_human_confirmation(
    checkpoint: str,
    question: str,
    editable_fields: list[str],
    auto_confirm_for_test: bool = False,
    project_id: str = "",
) -> dict:
    """Return user confirmation state for a checkpoint.

    In production this would block on UI input. For orchestration, we either
    auto-confirm (tests) or return pending state with editable fields echoed.
    """
    project_id = project_id or _gen_project_id()
    trace_write_event(
        "human_checkpoint_waiting",
        {"checkpoint": checkpoint, "editable_fields": editable_fields},
        project_id=project_id,
    )

    if auto_confirm_for_test:
        trace_write_event(
            "human_checkpoint_confirmed",
            {"checkpoint": checkpoint, "user_changes": {}},
            project_id=project_id,
        )
        return {
            "checkpoint": checkpoint,
            "confirmed": True,
            "auto_confirmed": True,
            "user_changes": {},
            "editable_fields": editable_fields,
        }

    # Production: defer to caller / UI; here we return pending with question payload.
    return {
        "checkpoint": checkpoint,
        "confirmed": False,
        "auto_confirmed": False,
        "question": question,
        "editable_fields": editable_fields,
    }


# ---------------------------------------------------------------------------
# Step 3: problem_decompose
# ---------------------------------------------------------------------------

def problem_decompose(topic_parse: dict) -> dict:
    """Sub-question decomposition via LLM.

    Falls back to a minimal heuristic decomposition if LLM unavailable —
    the fallback still respects the PROBLEM_DECOMPOSE_SCHEMA shape so downstream
    consumers can rely on field presence.
    """
    raw_topic = topic_parse.get("raw_topic", "")
    prompt = problem_decompose_user(json.dumps(topic_parse, ensure_ascii=False))
    llm_out = _llm_or_empty(prompt, problem_decompose_system())

    if llm_out and isinstance(llm_out.get("sub_questions"), list) and llm_out["sub_questions"]:
        return llm_out

    # ponytail: minimal 3-question heuristic fallback (not 4 — LLM-first SOP asks 4
    # but heuristic gets us >=3 to keep orchestrator happy; add dynamic 4th when LLM
    # measurably falls below prompt requirement)
    return {
        "sub_questions": [
            {
                "id": "sq1",
                "question": f"针对 {raw_topic}, 当前主流方法有哪些?",
                "priority": 1,
                "search_intent": "core_papers",
                "required_atoms": {"method": topic_parse.get("method_terms", []),
                                   "task": topic_parse.get("task_terms", [])},
                "success_signal": "至少有 2 篇近 3 年顶会/顶刊方法",
                "failure_signal": "检索不到近 3 年论文",
            },
            {
                "id": "sq2",
                "question": f"{raw_topic} 的主流公开数据集/基准是哪些?",
                "priority": 2,
                "search_intent": "datasets",
                "required_atoms": {"data": ["dataset", "benchmark"]},
                "success_signal": "至少有 1 个公开可用数据集",
                "failure_signal": "没有公开数据集",
            },
            {
                "id": "sq3",
                "question": f"{raw_topic} 是否有可复现的工程代码?",
                "priority": 3,
                "search_intent": "github_repos",
                "required_atoms": {"method": ["implementation", "code"]},
                "success_signal": "至少有 1 个 stars>=20 的 repo",
                "failure_signal": "无可用 code",
            },
        ],
        "graduation_safe_path": "基于公开数据集复现 baseline 方法",
        "high_risk_path": "提出新方法并验证",
        "human_checkpoints": ["domain_route", "data_availability"],
    }


# ---------------------------------------------------------------------------
# Step 4: search_strategy_build
# ---------------------------------------------------------------------------

def search_strategy_build(
    topic_parse: dict,
    problem_decomp: dict,
) -> dict:
    """Build a search strategy via LLM, ensure minimum queries."""
    prompt = search_strategy_user(
        json.dumps(topic_parse, ensure_ascii=False),
        json.dumps(problem_decomp, ensure_ascii=False),
    )
    llm_out = _llm_or_empty(prompt, search_strategy_system())

    if llm_out and isinstance(llm_out.get("search_strategies"), list) and llm_out["search_strategies"]:
        strategy = llm_out
    else:
        # ponytail: heuristic fallback — reuse research_query_expander for query list.
        from .retrieval.research_query_expander import expand_topic
        raw = topic_parse.get("raw_topic", "")
        expanded = expand_topic(raw)
        strategy = {
            "topic": raw,
            "domain_route": topic_parse.get("domain_route", "unknown"),
            "search_strategies": [
                {"name": "core_papers", "target_type": "paper",
                 "queries": expanded.paper_queries[:5],
                 "preferred_tools": ["arxiv", "openalex"],
                 "max_results_per_query": 8,
                 "why": "覆盖核心论文"},
                {"name": "datasets", "target_type": "dataset",
                 "queries": expanded.dataset_queries[:4],
                 "preferred_tools": ["huggingface", "kaggle"],
                 "max_results_per_query": 5,
                 "why": "覆盖公开数据集"},
                {"name": "github_repos", "target_type": "repo",
                 "queries": expanded.repo_queries[:4],
                 "preferred_tools": ["github"],
                 "max_results_per_query": 8,
                 "why": "覆盖可复现代码"},
            ],
            "negative_filters": topic_parse.get("negative_domains", []),
            "source_policy": {"arxiv": True, "semantic_scholar": True,
                              "github": True, "kaggle": True,
                              "hf_datasets": True, "papers_with_code": True},
            "clarification_questions": topic_parse.get("needs_clarification", []),
        }

    # Ensure minimum queries per strategy
    if _HAS_QUERY_BUILDER:
        try:
            strategy = ensure_minimum_queries(strategy)
        except Exception as exc:
            logger.warning("ensure_minimum_queries failed: %s", exc)

    pid = topic_parse.get("_project_id", _gen_project_id())
    trace_write_event(
        "search_strategy_created",
        {"strategy_count": len(strategy.get("search_strategies", [])),
         "query_count": sum(len(s.get("queries", [])) for s in strategy.get("search_strategies", [])),
         "domain_route": strategy.get("domain_route", "unknown")},
        project_id=pid,
    )
    return strategy


# ---------------------------------------------------------------------------
# Step 5: collect_candidates
# ---------------------------------------------------------------------------

async def collect_candidates(
    search_strategy: dict,
    project_id: str = "",
) -> dict:
    """Run paper/dataset/repo searches in parallel. Returns grouped results.

    Falls through to heuristic-empty lists if queries absent — orchestrator
    never crashes on adapter failure (router already swallows per-source errors).
    """
    project_id = project_id or _gen_project_id()
    strategies = search_strategy.get("search_strategies", [])

    paper_qs: list[str] = []
    dataset_qs: list[str] = []
    repo_qs: list[str] = []
    for s in strategies:
        name = s.get("name", "")
        qs = s.get("queries", []) or []
        if name == "core_papers" or "paper" in s.get("target_type", ""):
            paper_qs.extend(qs)
        elif name == "datasets" or "dataset" in s.get("target_type", ""):
            dataset_qs.extend(qs)
        elif name == "github_repos" or "repo" in s.get("target_type", ""):
            repo_qs.extend(qs)

    # De-dup queries, cap to avoid adapter overload
    paper_qs = list(dict.fromkeys(paper_qs))[:6]
    dataset_qs = list(dict.fromkeys(dataset_qs))[:4]
    repo_qs = list(dict.fromkeys(repo_qs))[:4]

    papers, datasets, repos = await asyncio.gather(
        search_papers(paper_qs, project_id=project_id) if paper_qs else asyncio.sleep(0, result=[]),
        search_datasets(dataset_qs, project_id=project_id) if dataset_qs else asyncio.sleep(0, result=[]),
        search_repos(repo_qs, project_id=project_id) if repo_qs else asyncio.sleep(0, result=[]),
    )

    # Normalize: search_papers etc are typed as list[dict]; gather might return coroutine futures.
    paper_results = papers if isinstance(papers, list) else []
    dataset_results = datasets if isinstance(datasets, list) else []
    repo_results = repos if isinstance(repos, list) else []

    # ponytail: tag each candidate with type for downstream screen_candidates
    candidates: list[dict] = []
    for p in paper_results:
        candidates.append({**p, "_type": "paper"})
    for d in dataset_results:
        candidates.append({**d, "_type": "dataset"})
    for r in repo_results:
        candidates.append({**r, "_type": "repo"})

    return {
        "papers": paper_results,
        "datasets": dataset_results,
        "repos": repo_results,
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Step 6: screen_candidates
# ---------------------------------------------------------------------------

def screen_candidates(
    topic_parse: dict,
    candidates: list[dict],
) -> dict:
    """Screen candidates via LLM. Keep only those in original input list.

    Falls back to simple keyword-overlap scoring if LLM unavailable. Always
    enforces the schema-defined shape.
    """
    if not candidates:
        return {
            "shortlist": [],
            "rejected": [],
            "need_retry_queries": [],
            "need_human_confirmation": True,
        }

    # Serialize candidates as JSONL for the prompt
    candidates_jsonl = "\n".join(json.dumps(c, ensure_ascii=False) for c in candidates)

    prompt = candidate_screen_user(
        json.dumps(topic_parse, ensure_ascii=False),
        candidates_jsonl,
    )
    llm_out = _llm_or_empty(prompt, candidate_screen_system())

    if llm_out and isinstance(llm_out.get("shortlist"), list):
        # ponytail: safety net — drop any shortlist entries whose candidate_id
        # isn't in the original input. LLM might invent IDs.
        original_ids = {c.get("candidate_id") or c.get("id") or c.get("_id") for c in candidates}
        original_ids = {i for i in original_ids if i}
        valid: list[dict] = []
        invalid_ids: list[str] = []
        for entry in llm_out.get("shortlist", []):
            cid = entry.get("candidate_id")
            if cid in original_ids:
                valid.append(entry)
            else:
                invalid_ids.append(cid or "<unknown>")
        llm_out["shortlist"] = valid
        if invalid_ids:
            llm_out.setdefault("rejected", []).extend(
                {"candidate_id": cid, "reason": "not_in_input"} for cid in invalid_ids
            )
        screened = llm_out
    else:
        # ponytail: heuristic fallback — score each candidate by atom overlap.
        atoms_en = [a.lower() for a in topic_parse.get("query_atoms_en", [])]
        atoms_zh = [a.lower() for a in topic_parse.get("query_atoms_zh", [])]

        def _score(c: dict) -> float:
            text_parts = [
                (c.get("title") or "").lower(),
                (c.get("description") or "").lower(),
                " ".join(c.get("tags") or []) if isinstance(c.get("tags"), list) else "",
                " ".join(c.get("matched_atoms") or []) if isinstance(c.get("matched_atoms"), list) else "",
            ]
            text = " ".join(text_parts)
            score = 0.0
            for a in atoms_en + atoms_zh:
                if a and a in text:
                    score += 0.2
            return min(score, 1.0)

        shortlist: list[dict] = []
        rejected: list[dict] = []
        for c in candidates:
            cid = c.get("candidate_id") or c.get("id") or c.get("_id") or ""
            s = _score(c)
            if s >= 0.2:
                shortlist.append({
                    "candidate_id": cid,
                    "candidate_type": c.get("_type", "paper"),
                    "relevance_score": round(s, 2),
                    "quality_score": 0.5,
                    "graduation_fit": "medium" if s >= 0.4 else "low",
                    "matched_atoms": [],
                    "keep_reason": f"atom_overlap={s:.2f}",
                    "risk_reason": "" if s >= 0.4 else "low_signal",
                    "must_verify": [],
                })
            else:
                rejected.append({"candidate_id": cid, "reason": "low_overlap"})

        # Sort by relevance desc, cap at top 10
        shortlist.sort(key=lambda x: x["relevance_score"], reverse=True)
        shortlist = shortlist[:10]

        screened = {
            "shortlist": shortlist,
            "rejected": rejected,
            "need_retry_queries": [],
            "need_human_confirmation": False,
        }

    pid = topic_parse.get("_project_id", _gen_project_id())
    trace_write_event(
        "candidate_screen_completed",
        {"input_count": len(candidates),
         "kept_count": len(screened.get("shortlist", [])),
         "rejected_count": len(screened.get("rejected", []))},
        project_id=pid,
    )
    return screened


# ---------------------------------------------------------------------------
# Step 7: direction_advice
# ---------------------------------------------------------------------------

def direction_advice(
    topic_parse: dict,
    shortlist: list[dict],
    gap_report: dict | None = None,
) -> dict:
    """Generate graduation-friendly direction advice via LLM.

    gap_report may be empty if no explicit gap analysis ran.
    Returns the direction_advice schema; stops here — no proposal.
    """
    gap = gap_report or {"missing_types": [], "retry_queries": []}
    prompt = direction_advice_user(
        json.dumps(topic_parse, ensure_ascii=False),
        json.dumps(shortlist, ensure_ascii=False),
        json.dumps(gap, ensure_ascii=False),
    )
    llm_out = _llm_or_empty(prompt, direction_advice_system())

    if llm_out and isinstance(llm_out.get("directions"), list) and llm_out["directions"]:
        advice = llm_out
    else:
        # ponytail: minimal heuristic advice — 1 safe + 1 optional + 1 fallback
        advice = {
            "directions": [
                {
                    "id": "dir_safe",
                    "title": "复现现有 baseline 方法",
                    "route_type": "graduation_safe",
                    "graduation_fit": "high",
                    "confidence": 0.6,
                    "bound_evidence_ids": [s.get("candidate_id") for s in shortlist[:3]
                                          if s.get("candidate_id")],
                    "recommended_baselines": [],
                    "suggested_modules": [],
                    "why_graduation_friendly": "基于已有候选复现, 工作量可控, 答辩可演示",
                    "risk_reasons": ["依赖公开代码可复现性"],
                    "user_must_confirm": ["确认数据可获得性"],
                },
                {
                    "id": "dir_opt",
                    "title": "在 baseline 之上做轻量改进",
                    "route_type": "optional_enhancement",
                    "graduation_fit": "medium",
                    "confidence": 0.4,
                    "bound_evidence_ids": [s.get("candidate_id") for s in shortlist[:2]
                                          if s.get("candidate_id")],
                    "recommended_baselines": [],
                    "suggested_modules": [],
                    "why_graduation_friendly": "在已有基础上改造, 比 baseline 增量明显",
                    "risk_reasons": ["改进点需明确可量化"],
                    "user_must_confirm": ["改进思路是否可行"],
                },
            ],
            "stop_reason": "ready" if shortlist else "need_more_search",
        }

    pid = topic_parse.get("_project_id", _gen_project_id())
    best = max(advice.get("directions", []), key=lambda d: d.get("confidence", 0), default={})
    trace_write_event(
        "direction_advice_ready",
        {"direction_count": len(advice.get("directions", [])),
         "best_route": best.get("id", "<none>"),
         "confidence": best.get("confidence", 0.0)},
        project_id=pid,
    )
    return advice


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_research_plan(
    raw_topic: str,
    student_context: dict | None = None,
    auto_confirm_for_test: bool = False,
) -> dict:
    """Full pipeline: parse → decompose → strategy → collect → screen → advise.

    Args:
        raw_topic: Student's raw thesis topic text.
        student_context: Optional dict with major / year / tools_known / local_case_hints.
        auto_confirm_for_test: If True, all human checkpoints auto-confirm.

    Returns:
        Dict with topic_parse, problem_decompose, search_strategy, candidates,
        screening, direction_advice, plus a `_project_id` field for trace lookup.
    """
    project_id = _gen_project_id()

    # 1. parse
    topic = topic_understand(raw_topic, student_context=student_context,
                             project_id=project_id)

    # 2. checkpoint: topic_parse
    confirm_topic = ask_human_confirmation(
        "topic_parse",
        question="请确认题目理解是否正确: " + topic.get("normalized_topic", raw_topic),
        editable_fields=["normalized_topic", "domain_route", "object_terms"],
        auto_confirm_for_test=auto_confirm_for_test,
        project_id=project_id,
    )
    if not confirm_topic.get("confirmed", False):
        return {"_status": "blocked", "_block_reason": "topic_parse_pending",
                "topic_parse": topic, "_project_id": project_id}

    # 3. decompose
    problem = problem_decompose(topic)

    # 4. strategy
    strategy = search_strategy_build(topic, problem)

    # 5. checkpoint: search_plan
    confirm_strategy = ask_human_confirmation(
        "search_plan",
        question="请确认检索策略: " + ", ".join(
            s.get("name", "") for s in strategy.get("search_strategies", [])
        ),
        editable_fields=["search_strategies", "negative_filters"],
        auto_confirm_for_test=auto_confirm_for_test,
        project_id=project_id,
    )
    if not confirm_strategy.get("confirmed", False):
        return {"_status": "blocked", "_block_reason": "search_plan_pending",
                "topic_parse": topic, "problem_decompose": problem,
                "search_strategy": strategy, "_project_id": project_id}

    # 6. collect
    collected = await collect_candidates(strategy, project_id=project_id)
    candidates = collected.get("candidates", [])

    # 7. screen
    screening = screen_candidates(topic, candidates)
    shortlist = screening.get("shortlist", [])

    # 8. direction advice
    gap_report = {
        "missing_types": [],
        "retry_queries": screening.get("need_retry_queries", []),
    }
    advice = direction_advice(topic, shortlist, gap_report)

    # 9. stop — no proposal generation
    return {
        "_status": "ok",
        "topic_parse": topic,
        "problem_decompose": problem,
        "search_strategy": strategy,
        "candidates_collected": collected,
        "screening": screening,
        "direction_advice": advice,
        "_project_id": project_id,
    }


__all__ = [
    "topic_understand",
    "ask_human_confirmation",
    "problem_decompose",
    "search_strategy_build",
    "collect_candidates",
    "screen_candidates",
    "direction_advice",
    "run_research_plan",
]


# ---------------------------------------------------------------------------
# Self-check (ponytail: assert-based __main__, fail loud if pipeline breaks)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Sync smoke: full pipeline runs without exceptions and returns shaped output.
    async def _smoke():
        result = await run_research_plan(
            "基于三维成像的损伤智能检测",
            student_context={"major": "土木工程", "year": "大四",
                             "tools_known": "Python, PyTorch"},
            auto_confirm_for_test=True,
        )
        assert "_status" in result, f"missing _status: {list(result.keys())}"
        assert result["topic_parse"]["raw_topic"] == "基于三维成像的损伤智能检测", (
            f"raw_topic mismatch: {result['topic_parse']['raw_topic']}"
        )
        assert result["topic_parse"]["domain_route"] == "vision_3d", (
            f"domain_route wrong: {result['topic_parse']['domain_route']}"
        )
        assert isinstance(result["problem_decompose"]["sub_questions"], list), (
            "sub_questions not a list"
        )
        assert len(result["problem_decompose"]["sub_questions"]) >= 3, (
            f"sub_questions < 3: {len(result['problem_decompose']['sub_questions'])}"
        )
        assert "search_strategies" in result["search_strategy"], (
            "search_strategy missing search_strategies"
        )
        assert "directions" in result["direction_advice"], (
            "direction_advice missing directions"
        )
        print("OK pipeline:", {
            "domain": result["topic_parse"]["domain_route"],
            "n_subq": len(result["problem_decompose"]["sub_questions"]),
            "n_strat": len(result["search_strategy"]["search_strategies"]),
            "n_cand": len(result["candidates_collected"]["candidates"]),
            "n_short": len(result["screening"]["shortlist"]),
            "n_dir": len(result["direction_advice"]["directions"]),
            "status": result["_status"],
        })

    asyncio.run(_smoke())
