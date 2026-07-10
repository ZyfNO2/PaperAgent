"""LangGraph node: verify paper candidates against the topic.

Uses the llm_router (fast_json profile) to apply re11_paper_verifier prompt;
produces verified_papers with per-keyword breakdown and drops rejected entries
into trace for auditability.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


from ._util import now_iso as _now_iso


def _call_verifier(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify candidates against topic using batched LLM calls.

    Batches candidates (batch_size=8) and sends each batch as a single LLM
    call, reducing wall-clock time from ~24×5s (sequential) to ~3×5s (3 batches
    with DeepSeek, parallel via ThreadPoolExecutor).
    """
    import concurrent.futures

    from apps.api.app.services import llm_router
    from apps.api.app.services.agents.prompts import re11_paper_verifier as P

    if not candidates:
        return []

    batch_size = max(1, _env_int("VERIFIER_BATCH_SIZE", 8))
    max_workers = max(1, min((len(candidates) + batch_size - 1) // batch_size,
                             _env_int("VERIFIER_MAX_WORKERS", 4)))
    timeout_s = max(5, _env_int("VERIFIER_TIMEOUT_S", 120))
    max_attempts = max(1, _env_int("VERIFIER_MAX_ATTEMPTS", 2))

    # Build batch prompts
    prompts = P.build_batch(topic, atoms, candidates, batch_size=batch_size)

    def _verify_batch(batch_idx: int) -> list[dict[str, Any]]:
        """Verify a batch of candidates; returns list of normalised verdict dicts."""
        built = prompts[batch_idx]
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                out = llm_router.call_json(
                    built["user"],
                    system=built["system"],
                    profile="fast_json",
                    max_tokens=3000,
                    timeout=timeout_s,
                    expected="list",
                    schema_hint='JSON array of objects: [{"title": str, "verdict": str, "hit_keywords": [str], "relation_to_topic": str, "reason": str}]',
                )
                verdicts = _normalise_verifier_output(out)
                if not verdicts and attempt + 1 < max_attempts:
                    continue
                return verdicts
            except Exception as exc:
                last_exc = exc
                logger.debug("verifier batch %s attempt %s failed: %s",
                             batch_idx, attempt, type(exc).__name__)
        if last_exc is not None:
            logger.warning("verifier batch %s final failure: %s",
                           batch_idx, type(last_exc).__name__)
        return []

    all_verdicts: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_verify_batch, i): i for i in range(len(prompts))}
        for future in concurrent.futures.as_completed(futures):
            try:
                verdicts = future.result()
                all_verdicts.extend(verdicts)
            except Exception as exc:
                logger.warning("verifier batch raised: %s", exc)

    return all_verdicts


def _normalise_verifier_output(out: Any) -> list[dict[str, Any]]:
    """Walk through the many shapes the verifier LLM can emit."""
    if out is None:
        return []
    if isinstance(out, dict):
        for key in ("verdicts", "verified", "candidates", "results"):
            cand = out.get(key)
            if isinstance(cand, list):
                return [v for v in cand if isinstance(v, dict)]
        return [out]
    if isinstance(out, list):
        return [v for v in out if isinstance(v, dict)]
    if isinstance(out, str):
        found = (re.search(r"\[.*\]", out, re.DOTALL)
                 or re.search(r"\{.*\}", out, re.DOTALL))
        if not found:
            return []
        try:
            return _normalise_verifier_output(json.loads(found.group(0)))
        except json.JSONDecodeError:
            return []
def verify_node(state: ResearchState) -> dict[str, Any]:
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}

    # Determine candidates based on verify_scope (explicit) or citation_done (legacy).
    # verify_scope ∈ {"search", "expanded", "repair"} — set by the routing function
    # to disambiguate the three call paths into verify_node:
    #   search   → quality_filter → verify  (first round, candidates = paper_candidates)
    #   expanded → citation_expander → verify when n_expanded > 0
    #   repair  → paper_retriever → quality_filter → verify (repair loop)
    verify_scope = state.get("verify_scope") or ""
    citation_done = state.get("citation_expansion_done", False)

    if verify_scope == "expanded":
        # After citation_expander with n_expanded > 0: ONLY verify expanded papers.
        # Never fall back to paper_candidates — that would wipe existing accepted.
        candidates = list(state.get("expanded_papers") or [])
    elif verify_scope == "repair":
        # Repair loop: candidates are the freshly-repaired paper_candidates.
        candidates = list(state.get("paper_candidates") or [])
    elif verify_scope == "search" or not citation_done:
        # First round: verify paper_candidates as-is.
        candidates = list(state.get("paper_candidates") or [])
    else:
        # citation_done=True but verify_scope not "expanded": avoid re-verifying
        # paper_candidates when expanded_papers is empty — this path should be
        # prevented by the conditional edge route_after_citation_expander, but
        # we guard here as well for defence in depth.
        expanded = list(state.get("expanded_papers") or [])
        if expanded:
            candidates = expanded
        else:
            candidates = []  # Guard: do not fall back to paper_candidates

    user_constraints = state.get("user_constraints") or {}
    if isinstance(user_constraints, dict):
        verify_limit = int(user_constraints.get("max_verify_candidates", len(candidates)) or len(candidates))
        verify_limit = max(0, min(len(candidates), verify_limit))
        candidates = candidates[:verify_limit]
    t0 = time.time()

    trace: dict[str, Any] = {
        "node": "verify",
        "started_at": _now_iso(),
        "input_summary": {"n_candidates": len(candidates), "topic_len": len(topic),
                          "verify_scope": verify_scope or ("expanded" if citation_done else "search"),
                          "citation_done": citation_done},
        "output_summary": {},
        "tool_calls": [{"tool": "re11_paper_verifier.llm", "profile": "fast_json"}],
        "errors": [],
        "provider": "fast_json",
        "state_keys": ["verified_papers", "weak_papers", "paper_candidates",
                        "trace_events", "errors", "provider_profile", "verify_scope"],
    }
    errors: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    try:
        verdicts = _call_verifier(topic, atoms, candidates)
        # Build title→candidate index to carry over identifiers (doi, paper_id, etc.)
        _candidate_by_title: dict[str, dict[str, Any]] = {}
        for c in candidates:
            t = (c.get("title") or c.get("name") or "").strip().lower()
            if t:
                _candidate_by_title[t] = c
        # Map loose schema to normalized candidate.
        keep = []
        weak = []
        rejected = []
        keep_titles: set[str] = set()
        keep_urls: set[str] = set()
        for v in verdicts:
            title = (v.get("title") or v.get("name") or "").strip()
            if not title:
                continue
            verdict = (v.get("verdict") or "").lower()
            # Carry over identifiers from the original candidate
            orig = _candidate_by_title.get(title.lower(), {})
            item = {
                "title": title,
                "verdict": verdict,
                "hit_keywords": v.get("hit_keywords") or [],
                "unrelated_keywords": v.get("unrelated_keywords") or [],
                "related_keywords": v.get("related_keywords") or [],
                "source_type": v.get("source_type") or "paper",
                "relation_to_topic": v.get("relation_to_topic") or "none",
                "url_missing": bool(v.get("url_missing")),
                "needs_human_confirm": bool(v.get("needs_human_confirm")),
                "reason": v.get("reason") or "",
                # Re1.3: carry over identifiers for citation_expander
                "doi": orig.get("doi") or v.get("doi"),
                "url": orig.get("url") or v.get("url"),
                "source": orig.get("source") or v.get("source"),
                "paper_id": orig.get("paper_id") or v.get("paper_id"),
                "arxiv_id": orig.get("arxiv_id") or v.get("arxiv_id"),
                "citation_count": orig.get("citation_count") or v.get("citation_count") or 0,
                "abstract": orig.get("abstract") or v.get("abstract") or "",
            }
            # Re2.2-fix: deduplicate by title + URL in first round too
            dedup_key = title.lower().strip()
            url_key = (item.get("url") or "").lower().strip()
            if dedup_key in keep_titles:
                continue
            if url_key and url_key in keep_urls:
                continue
            keep_titles.add(dedup_key)
            if url_key:
                keep_urls.add(url_key)
            if verdict == "accept":
                keep.append(item)
            elif verdict == "weak_reject":
                weak.append(item)
            else:
                rejected.append(item)
        verified = keep
        trace["output_summary"] = {
            "n_accept": len(keep),
            "n_weak_reject": len(weak),
            "n_reject": len(rejected),
        }
    except Exception as exc:
        # SOP §15 / 自查方案 §2: when verification fails we MUST NOT forward
        # raw candidates as verified. Return an empty verified list so the
        # quarantine path (the rejection list) carries the titles forward.
        logger.exception("verify_node LLM call failed — candidates quarantined")
        rejected_titles = [
            c.get("title") or c.get("name") or "" for c in candidates
        ]
        errors.append({"node": "verify", "error": f"LLMUnavailable:{type(exc).__name__}"})
        trace["errors"].append({
            "phase": "llm_call",
            "error": f"{type(exc).__name__}",
            "action": "quarantine_all",
            "quarantined_titles": rejected_titles[:50],
        })
        trace["output_summary"] = {
            "n_accept": 0,
            "n_reject_or_weak": len(rejected_titles),
            "note": "verify_failed_all_quarantined",
        }
        verified = []

    trace["ended_at"] = _now_iso()

    trace["elapsed_s"] = round(time.time() - t0, 3)


    # Re1.3: merge verified_papers in second round
    if citation_done:
        existing_verified = list(state.get("verified_papers") or [])
        existing_weak = list(state.get("weak_papers") or [])

        # Re2.2 fix: deduplicate by title before merging
        seen_titles: set[str] = set()
        for p in existing_verified + existing_weak:
            t = (p.get("title") or "").strip().lower()
            if t:
                seen_titles.add(t)

        deduped_verified = []
        deduped_weak = []
        for p in verified:
            t = (p.get("title") or "").strip().lower()
            if t and t in seen_titles:
                continue  # skip duplicate
            deduped_verified.append(p)
            seen_titles.add(t)
        for p in weak:
            t = (p.get("title") or "").strip().lower()
            if t and t in seen_titles:
                continue
            deduped_weak.append(p)
            seen_titles.add(t)

        merged_verified = existing_verified + deduped_verified
        merged_weak = existing_weak + deduped_weak

        return {
            "verified_papers": merged_verified,
            "weak_papers": merged_weak,
            "paper_candidates": candidates,
            "trace_events": [trace],
            "errors": errors,
            "provider_profile": "fast_json",
        }


    return {

        "verified_papers": verified,
        "weak_papers": weak,
        "paper_candidates": candidates,

        "trace_events": [trace],

        "errors": errors,

        "provider_profile": "fast_json",

    }
