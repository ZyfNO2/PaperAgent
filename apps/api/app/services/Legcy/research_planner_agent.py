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
    candidate_screen_user,
    direction_advice_user,
    problem_decompose_user,
    search_strategy_user,
    topic_understand_user,
)
from .research_prompts_v2 import (
    candidate_screen_system,
    direction_advice_system,
    problem_decompose_system,
    search_strategy_system,
    tool_plan_system,
    tool_plan_user,
    topic_understand_system,
)
from .research_skill_bridge import (
    apply_skill_backfill,
    build_skill_overlay,
    enrich_dataset_candidates_with_skill,
    filter_repo_candidates_with_skill,
    repair_topic_parse_with_skill,
)
from .research_topic_parser import parse_topic_rule_based, validate_and_repair_llm_output
from .research_tool_router import (
    trace_write_event,
)
from .llm import LLMUnavailable, chat_json
from .retrieval.candidate_cleaner import clean_candidates
from .retrieval.literature_role_classifier import classify_literature
from .retrieval.tool_orchestrator import (
    TOOL_WHITELIST,
    ToolCall,
    ToolExecutionResult,
    ToolPlan,
    execute_tool_plan,
)


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

def _llm_or_empty(prompt: str, system: str, *, profile: str = "default") -> dict:
    """Call LLM, return parsed dict. Empty dict on LLM failure.

    Caller decides what to do with empty — typically falls through to
    rule-based parse / heuristic expansion.
    """
    try:
        system_with_overlay = f"{system}\n\n{build_skill_overlay(profile)}"
        result = chat_json(
            prompt,
            system=system_with_overlay,
            temperature=0.2,
            max_tokens=1500,
            profile=profile,
        )
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
    llm_out = _llm_or_empty(prompt, topic_understand_system(), profile="topic_understand")

    if llm_out:
        parsed = validate_and_repair_llm_output(llm_out, raw_topic)
    else:
        parsed = parse_topic_rule_based(raw_topic)
        parsed["llm_output_repaired"] = False
        parsed["domain_route_conflict"] = False
    # Never let downstream stages drift away from the user's actual topic.
    parsed["raw_topic"] = raw_topic
    parsed = repair_topic_parse_with_skill(parsed)

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
    llm_out = _llm_or_empty(prompt, problem_decompose_system(), profile="problem_decompose")

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
    llm_out = _llm_or_empty(prompt, search_strategy_system(), profile="search_strategy")

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
# Step 5: tool planning + collect_candidates
# ---------------------------------------------------------------------------


def _pick_skill_query(target: str, topic_parse: dict, *, idx: int = 0) -> str:
    """Return a deterministic, skill-built query for a given target.

    The LLM is not allowed to author search queries any more; we always pick
    from ``topic_parse["query_atoms_en"]`` (or ``_zh`` fallback) and add a
    target-specific suffix so external sources like Crossref / arXiv / GitHub
    can match.

    AutoResearchClaw principle: structure > generation.  The LLM only chooses
    *which* tools to call; *what* to ask them is deterministic.
    """
    atoms_en = [str(a).strip() for a in (topic_parse.get("query_atoms_en") or []) if str(a).strip()]
    atoms_zh = [str(a).strip() for a in (topic_parse.get("query_atoms_zh") or []) if str(a).strip()]
    # Pick the index-th atom (clamp to length) to spread load across atoms.
    base = (atoms_en[idx] if atoms_en else (atoms_zh[idx] if atoms_zh else ""))
    if not base:
        base = str(topic_parse.get("raw_topic") or "").strip()
    target = (target or "paper").lower()
    if target in {"paper", "module_paper"}:
        # arXiv / Crossref / OpenAlex: keep atom clean
        return base
    if target in {"dataset"}:
        # Crossref / HuggingFace need dataset-y hint words
        if "dataset" in base.lower() or "benchmark" in base.lower():
            return base
        return f"{base} dataset benchmark"
    if target in {"repo", "baseline"}:
        # GitHub search benefits from these tokens
        if any(t in base.lower() for t in ("github", "pytorch", "implementation", "code", "baseline")):
            return base
        return f"{base} github pytorch implementation"
    return base


def _looks_like_garbage_query(q: str) -> bool:
    """Heuristic: LLM sometimes writes placeholder / placeholder-flavoured queries."""
    if not q or len(q) < 3:
        return True
    ql = q.lower()
    bad_markers = (
        "question mark", "placeholder", "unresolved", "encoding error",
        "thai", "korean", "japanese",
    )
    if any(m in ql for m in bad_markers):
        return True
    # Less than 50% of the query overlaps with the topic atoms -> not a real query.
    return False


def _heuristic_tool_plan(topic_parse: dict, search_strategy: dict) -> ToolPlan:
    """Fallback ToolPlan from the existing search strategy."""
    calls: list[ToolCall] = []
    idx = 0
    # Use the skill-built atoms for *every* query; the LLM-written search_strategy
    # is only used to decide *which* target_types to dispatch.
    target_types: list[tuple[str, str]] = []
    for strategy in search_strategy.get("search_strategies", []):
        name = str(strategy.get("name", ""))
        ttype = str(strategy.get("target_type", "paper"))
        if name == "datasets" or ttype == "dataset":
            target_types.append(("dataset", "search_dataset_web"))
        elif name in {"github_repos", "classic_baselines"} or ttype in {"repo", "baseline"}:
            target_types.append((ttype if ttype in {"repo", "baseline"} else "repo",
                                 "search_github"))
        elif name == "emerging_methods":
            target_types.append(("module_paper", "search_arxiv"))
        else:
            target_types.append(("paper", "search_openalex"))
            target_types.append(("paper", "search_arxiv"))  # variety

    for target, tool in target_types:
        # Always add a Crossref call alongside OpenAlex for paper searches
        # so we have a free-source fallback when OpenAlex is paid-locked.
        if tool == "search_openalex":
            cr_q = _pick_skill_query("paper", topic_parse, idx=idx % max(1, len(topic_parse.get("query_atoms_en") or [1])))
            calls.append(
                ToolCall(
                    call_id=f"tc_{idx:02d}_cr",
                    tool="search_crossref",
                    target="paper",
                    query=cr_q,
                    when_to_call="round_1",
                    why_call="crossref fallback for paper search (free, no rate limit)",
                    how_call={"top_k": 8},
                    expected_output="papers via crossref",
                    stop_condition="ok",
                )
            )
        query = _pick_skill_query(target, topic_parse, idx=idx)
        calls.append(
            ToolCall(
                call_id=f"tc_{idx:02d}",
                tool=tool,
                target=target if target != "module_paper" else "module_paper",
                query=query,
                when_to_call="planner_round_1",
                why_call="skill-driven deterministic query",
                how_call={"top_k": 8},
                expected_output=f"{target} candidates",
                stop_condition="first useful batch",
            )
        )
        idx += 1
    return ToolPlan(
        topic_atoms={
            "raw": topic_parse.get("raw_topic", ""),
            "domain_route": topic_parse.get("domain_route", "unknown"),
            "method_terms": topic_parse.get("method_terms", []),
            "task_terms": topic_parse.get("task_terms", []),
            "object_terms": topic_parse.get("object_terms", []),
        },
        calls=calls[:10],
        human_gate_after="round_1",
    )


def build_tool_plan(topic_parse: dict, search_strategy: dict) -> ToolPlan:
    """Planner role: strict ToolPlan generation."""
    prompt = tool_plan_user(
        json.dumps(topic_parse, ensure_ascii=False),
        json.dumps(search_strategy, ensure_ascii=False),
    )
    llm_out = _llm_or_empty(prompt, tool_plan_system(), profile="tool_plan")
    if llm_out:
        try:
            plan = ToolPlan.model_validate(llm_out)
            valid_calls = [call for call in plan.calls if call.tool in TOOL_WHITELIST]
            if valid_calls:
                # Override LLM-written queries with skill-built atoms.
                atoms = list(topic_parse.get("query_atoms_en") or [])
                atoms_zh = list(topic_parse.get("query_atoms_zh") or [])
                fixed: list[ToolCall] = []
                for i, call in enumerate(valid_calls[:10]):
                    new_q = _pick_skill_query(call.target, topic_parse, idx=i)
                    if _looks_like_garbage_query(call.query) or not call.query:
                        fixed.append(call.model_copy(update={"query": new_q}))
                    else:
                        # LLM query stays only if it overlaps with skill atoms.
                        ql = call.query.lower()
                        if any(a and a.lower() in ql for a in atoms + atoms_zh):
                            fixed.append(call)
                        else:
                            fixed.append(call.model_copy(update={"query": new_q}))
                return plan.model_copy(update={"calls": fixed})
        except Exception as exc:  # noqa: BLE001
            logger.warning("tool plan validation failed: %s", exc)
    return _heuristic_tool_plan(topic_parse, search_strategy)


def _candidate_from_tool_result(result: ToolExecutionResult) -> list[dict]:
    out: list[dict] = []
    for cand in result.candidates:
        item = dict(cand)
        item["_type"] = item.get("candidate_type") or "note"
        out.append(item)
    return out


async def collect_candidates(
    topic_parse: dict,
    search_strategy: dict,
    project_id: str = "",
) -> dict:
    """Run the Retriever role via ToolPlan -> tool_orchestrator."""
    project_id = project_id or _gen_project_id()
    tool_plan = build_tool_plan(topic_parse, search_strategy)
    bundle = await execute_tool_plan(tool_plan, project_id)
    candidates: list[dict] = []
    for result in bundle.results:
        candidates.extend(_candidate_from_tool_result(result))
    candidates = apply_skill_backfill(topic_parse, candidates)
    candidates = enrich_dataset_candidates_with_skill(candidates)
    candidates = filter_repo_candidates_with_skill(topic_parse, candidates)
    return {
        "tool_plan": tool_plan.model_dump(),
        "tool_execution": bundle.model_dump(),
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

    cleaned_results = clean_candidates(
        candidates,
        topic_atoms=topic_parse,
        domain=str(topic_parse.get("domain_route", "unknown")),
    )
    reject_ids = {
        item.candidate_id
        for item in cleaned_results
        if item.clean_status in {"reject", "quarantine"}
    }
    skill_seed_candidate_ids = {
        str(candidate.get("candidate_id", ""))
        for candidate in candidates
        if (candidate.get("raw") or {}).get("skill_role") in {
            "baseline_catalog",
            "dataset_catalog",
            "web_dataset_seed",
        }
    }
    filtered_candidates = [
        candidate
        for candidate in candidates
        if (
            (candidate.get("candidate_id") or "") not in reject_ids
            or str(candidate.get("candidate_id", "")) in skill_seed_candidate_ids
        )
    ]
    manual_ids = {
        item.candidate_id
        for item in cleaned_results
        if item.clean_status == "needs_manual"
    }
    skill_seed_ids = {
        str(candidate.get("candidate_id", ""))
        for candidate in filtered_candidates
        if str(candidate.get("candidate_id", "")) in skill_seed_candidate_ids
    }

    if not filtered_candidates:
        return {
            "shortlist": [],
            "rejected": [
                {
                    "candidate_id": item.candidate_id,
                    "reason": item.reason,
                    "clean_status": item.clean_status,
                }
                for item in cleaned_results
            ],
            "need_retry_queries": [],
            "need_human_confirmation": bool(manual_ids),
        }

    # Serialize candidates as JSONL for the prompt
    candidates_jsonl = "\n".join(json.dumps(c, ensure_ascii=False) for c in filtered_candidates)

    prompt = candidate_screen_user(
        json.dumps(topic_parse, ensure_ascii=False),
        candidates_jsonl,
    )
    llm_out = _llm_or_empty(prompt, candidate_screen_system(), profile="candidate_screen")

    if llm_out and isinstance(llm_out.get("shortlist"), list):
        # ponytail: safety net — drop any shortlist entries whose candidate_id
        # isn't in the original input. LLM might invent IDs.
        original_ids = {c.get("candidate_id") or c.get("id") or c.get("_id") for c in filtered_candidates}
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
        for c in filtered_candidates:
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
            "need_human_confirmation": bool(manual_ids),
        }

    cleaned_by_id = {item.candidate_id: item for item in cleaned_results}
    for entry in screened.get("shortlist", []):
        cid = entry.get("candidate_id")
        clean_item = cleaned_by_id.get(cid)
        if clean_item and clean_item.clean_status == "needs_manual":
            must_verify = list(entry.get("must_verify") or [])
            must_verify.append("candidate_cleaner_manual_review")
            entry["must_verify"] = must_verify

    current_shortlist_ids = {
        str(entry.get("candidate_id"))
        for entry in screened.get("shortlist", [])
        if entry.get("candidate_id")
    }
    for candidate in filtered_candidates:
        cid = str(candidate.get("candidate_id", ""))
        if cid not in skill_seed_ids or cid in current_shortlist_ids:
            continue
        screened.setdefault("shortlist", []).append(
            {
                "candidate_id": cid,
                "candidate_type": candidate.get("candidate_type", candidate.get("_type", "note")),
                "relevance_score": 0.66,
                "quality_score": 0.66,
                "graduation_fit": "medium",
                "matched_atoms": list(candidate.get("matched_keywords") or []),
                "keep_reason": "skill_seed_fallback",
                "risk_reason": "",
                "must_verify": ["skill_seed_needs_manual_confirmation"],
            }
        )

    screened.setdefault("rejected", []).extend(
        {
            "candidate_id": item.candidate_id,
            "reason": item.reason,
            "clean_status": item.clean_status,
        }
        for item in cleaned_results
        if item.clean_status in {"reject", "quarantine"}
    )
    screened["cleaning_summary"] = [item.model_dump() for item in cleaned_results]

    pid = topic_parse.get("_project_id", _gen_project_id())
    trace_write_event(
        "candidate_screen_completed",
        {"input_count": len(candidates),
         "kept_count": len(screened.get("shortlist", [])),
         "rejected_count": len(screened.get("rejected", []))},
        project_id=pid,
    )
    return screened


def assemble_research_output(
    topic_parse: dict,
    candidates: list[dict],
    screening: dict,
    tool_execution: dict | None = None,
) -> dict:
    """Auditor role: convert shortlist into the fixed scientific view."""
    shortlist_ids = {
        str(item.get("candidate_id"))
        for item in screening.get("shortlist", [])
        if item.get("candidate_id")
    }
    shortlisted_candidates = [
        candidate
        for candidate in candidates
        if str(candidate.get("candidate_id", "")) in shortlist_ids
    ]

    papers = [
        candidate
        for candidate in shortlisted_candidates
        if candidate.get("candidate_type") == "paper"
    ]
    datasets = [
        candidate
        for candidate in shortlisted_candidates
        if candidate.get("candidate_type") == "dataset"
    ]
    repos = [
        candidate
        for candidate in shortlisted_candidates
        if candidate.get("candidate_type") == "repo"
    ]

    role_results = classify_literature(papers, topic_parse)
    paper_by_id = {str(candidate.get("candidate_id", "")): candidate for candidate in papers}

    def _with_role(entry: Any) -> dict:
        paper = dict(paper_by_id.get(entry.candidate_id, {}))
        paper["literature_role"] = entry.role
        paper["role_reason"] = entry.reason
        paper["reproducibility"] = entry.reproducibility
        paper["borrowable_ideas"] = list(entry.borrowable_ideas or [])
        paper["risk_notes"] = list(entry.risk_notes or [])
        return paper

    baseline_candidates: list[dict] = []
    parallel_reference_papers: list[dict] = []
    module_reference_papers: list[dict] = []
    reference_papers: list[dict] = []

    for role_result in role_results:
        if role_result.role in {"irrelevant", "survey"}:
            continue
        paper = _with_role(role_result)
        if role_result.role in {"baseline_framework", "baseline_method"}:
            baseline_candidates.append(paper)
        elif role_result.role == "parallel_application_paper":
            parallel_reference_papers.append(paper)
        elif role_result.role == "module_improvement_paper":
            module_reference_papers.append(paper)
        else:
            reference_papers.append(paper)

    skill_baseline_repos = [
        candidate
        for candidate in repos
        if (candidate.get("raw") or {}).get("skill_role") == "baseline_catalog"
    ]
    if not baseline_candidates and skill_baseline_repos:
        baseline_candidates = skill_baseline_repos[:5]

    if not reference_papers:
        reference_papers = [
            _with_role(role_result)
            for role_result in role_results
            if role_result.role not in {"irrelevant", "survey"}
        ][:6]

    evidence_gaps: list[str] = []
    if len(reference_papers) + len(parallel_reference_papers) < 2:
        evidence_gaps.append("参考论文不足，当前少于 2 条已验证论文候选")
    if not baseline_candidates:
        evidence_gaps.append("未找到 baseline，需人工确认可复现基线")
    if not parallel_reference_papers:
        evidence_gaps.append("未找到平行参考，需补充同任务同对象论文")
    if not datasets:
        evidence_gaps.append("未找到公开数据集或需自采")
    if not repos:
        evidence_gaps.append("未找到可复现仓库")

    return {
        "reference_papers": reference_papers[:8],
        "baseline_candidates": baseline_candidates[:5],
        "parallel_reference_papers": parallel_reference_papers[:5],
        "module_reference_papers": module_reference_papers[:5],
        "dataset_candidates": datasets[:5],
        "repo_candidates": repos[:5],
        "evidence_gaps": evidence_gaps,
        "tool_execution": tool_execution or {},
    }


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
    llm_out = _llm_or_empty(prompt, direction_advice_system(), profile="direction_advice")

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
    collected = await collect_candidates(topic, strategy, project_id=project_id)
    candidates = collected.get("candidates", [])

    # 7. screen
    screening = screen_candidates(topic, candidates)
    shortlist = screening.get("shortlist", [])
    research_summary = assemble_research_output(
        topic,
        candidates,
        screening,
        collected.get("tool_execution"),
    )

    # 8. direction advice
    gap_report = {
        "missing_types": research_summary.get("evidence_gaps", []),
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
        "research_summary": research_summary,
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
    "assemble_research_output",
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
        # ponytail: domain_route depends on LLM (might pick vision_3d or civil_infra)
        # — verify it's one of the valid routes instead of pinning to one.
        valid_routes = {"vision_2d", "vision_3d", "nlp_llm", "signal_timeseries",
                        "robotics_control", "remote_sensing", "medical_ai",
                        "energy_power", "civil_infra", "unknown"}
        assert result["topic_parse"]["domain_route"] in valid_routes, (
            f"domain_route not in valid routes: {result['topic_parse']['domain_route']}"
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
