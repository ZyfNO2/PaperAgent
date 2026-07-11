"""LangGraph node: verify paper candidates against the topic — Re7.6 hardened.

Changes from original:
  - candidate_id assignment before LLM call (stable matching, not title fuzzy match)
  - coverage tracking: resolved_count / input_count
  - verification_failed state (distinct from "0 accepted")
  - partial batch handling: unresolved candidates preserved, not dropped
  - structured trace: raw_length, parse_stage, coverage, invalid_ids
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


def _assign_candidate_ids(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign stable candidate_id to each candidate for LLM output matching."""
    for i, c in enumerate(candidates):
        if "candidate_id" not in c:
            base = (c.get("paper_id") or c.get("doi") or c.get("arxiv_id") or
                    (c.get("title") or c.get("name") or "").strip()[:40])
            c["candidate_id"] = f"{base}_{i}" if base else f"cand_{i}"
    return candidates


def _filter_valid_verdicts(
    verdicts: list[dict[str, Any]],
    batch_ids: set[str],
    title_to_id: dict[str, str],
    diag: dict[str, Any],
) -> tuple[list[dict[str, Any]], int]:
    """Return verdicts whose candidate_id belongs to the batch, plus title-match count."""
    resolved_ids: set[str] = set()
    valid_verdicts: list[dict[str, Any]] = []
    title_matched = 0
    for v in verdicts:
        cid = v.get("candidate_id", "")
        if not cid:
            vtitle = (v.get("title") or v.get("name") or "").strip().lower()
            if vtitle and vtitle in title_to_id:
                cid = title_to_id[vtitle]
                v["candidate_id"] = cid
                title_matched += 1
        if not cid:
            continue
        if cid not in batch_ids:
            diag["invalid_ids"].append(cid)
            continue
        if cid in resolved_ids:
            continue
        resolved_ids.add(cid)
        valid_verdicts.append(v)
    return valid_verdicts, title_matched


def _call_verifier(
    topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify candidates. Returns (verdicts, diagnostics).

    Re7.6: unified router is the primary path; legacy llm_router.call_json is
    used only as a one-time fallback when the contract path itself fails.
    A successful contract call that yields zero valid verdicts is treated as
    `zero_coverage` immediately and does NOT trigger legacy fallback (SOP §2.3).

    Diagnostics:
      total_input / total_resolved / coverage / parse_stages / invalid_ids
      unresolved_ids / provider / model / contract_id
    """
    import concurrent.futures

    from apps.api.app.services import llm_router
    from apps.api.app.services.agents.prompts import re11_paper_verifier as P
    from apps.api.app.services.router.register_verification import register_verification_contract

    if not candidates:
        return [], {"total_input": 0, "total_resolved": 0, "coverage": 1.0,
                    "unresolved_ids": [], "provider": "", "model": "", "contract_id": ""}

    batch_size = max(1, _env_int("VERIFIER_BATCH_SIZE", 8))
    max_workers = max(1, min((len(candidates) + batch_size - 1) // batch_size,
                             _env_int("VERIFIER_MAX_WORKERS", 4)))
    timeout_s = max(5, _env_int("VERIFIER_TIMEOUT_S", 120))
    max_attempts = max(1, _env_int("VERIFIER_MAX_ATTEMPTS", 2))

    register_verification_contract()

    prompts = P.build_batch(topic, atoms, candidates, batch_size=batch_size)
    diag: dict[str, Any] = {
        "total_input": len(candidates),
        "total_resolved": 0,
        "coverage": 0.0,
        "parse_stages": [],
        "invalid_ids": [],
        "unresolved_ids": [],
        "raw_lengths": [],
        "batch_results": [],
        "provider": "",
        "model": "",
    }

    def _verify_batch(batch_idx: int) -> tuple[list[dict[str, Any]], dict]:
        built = prompts[batch_idx]
        batch_candidates = candidates[batch_idx * batch_size:(batch_idx + 1) * batch_size]
        batch_ids = {c["candidate_id"] for c in batch_candidates}
        title_to_id: dict[str, str] = {}
        for c in batch_candidates:
            t = (c.get("title") or c.get("name") or "").strip().lower()
            if t:
                title_to_id[t] = c["candidate_id"]

        for attempt in range(max_attempts):
            raw_str = ""
            out: Any = None
            try:
                if attempt == 0:
                    from apps.api.app.services.router import call_with_contract_list
                    contract_result = call_with_contract_list(
                        built["user"],
                        system=built["system"],
                        contract_id="verification-batch/v1",
                        max_tokens=3000,
                        timeout=timeout_s,
                    )
                    raw_str = json.dumps(contract_result.content, ensure_ascii=False, default=str) if contract_result.content is not None else ""
                    diag["provider"] = contract_result.provider_chain[0] if contract_result.provider_chain else ""
                    diag["model"] = contract_result.provider_chain[-1] if contract_result.provider_chain else ""
                    diag["contract_id"] = "verification-batch/v1"
                    if contract_result.success and isinstance(contract_result.content, list):
                        out = contract_result.content
                        # Re7.6 SOP §2.3: zero coverage from a successful contract call
                        # is a typed failure (verification_failed), not a reason to fall
                        # back to the legacy path and burn more tokens.
                        normalised = _normalise_verifier_output(out)
                        valid_now, _ = _filter_valid_verdicts(normalised, batch_ids, title_to_id, diag)
                        if not valid_now:
                            return [], {"batch": batch_idx, "parse_stage": "zero_coverage",
                                         "resolved": 0, "raw_length": len(raw_str),
                                         "expected": len(batch_candidates)}
                    elif contract_result.heuristic_fallback:
                        return [], {"batch": batch_idx, "parse_stage": "heuristic_fallback",
                                     "resolved": 0, "raw_length": 0, "error": contract_result.error}
                    else:
                        raise RuntimeError(f"verification contract failed: {contract_result.error}")
                else:
                    # Legacy fallback: one attempt only (contract failure / heuristic fallback)
                    out = llm_router.call_json(
                        built["user"],
                        system=built["system"],
                        profile="fast_json",
                        max_tokens=3000,
                        timeout=timeout_s,
                        expected="list",
                        schema_hint='JSON array of objects: [{"candidate_id": str, "verdict": str, "hit_keywords": [str], "relation_to_topic": str, "reason": str}]',
                    )
                    raw_str = json.dumps(out, ensure_ascii=False, default=str) if out is not None else ""
                    diag["provider"] = diag.get("provider") or "fast_json"
                    diag["contract_id"] = "legacy_fallback"
            except Exception as exc:
                logger.debug("verifier batch %s attempt %s failed: %s", batch_idx, attempt, type(exc).__name__)
                if attempt + 1 < max_attempts:
                    continue
                return [], {"batch": batch_idx, "error": str(exc), "raw_length": len(raw_str),
                             "parse_stage": "llm_unavailable", "resolved": 0}

            # Parse and validate
            verdicts = _normalise_verifier_output(out)
            valid_verdicts, title_matched = _filter_valid_verdicts(verdicts, batch_ids, title_to_id, diag)

            parse_stage = "resolved" if valid_verdicts else "empty_after_filter"
            batch_diag = {
                "batch": batch_idx, "raw_length": len(raw_str),
                "parse_stage": parse_stage, "resolved": len(valid_verdicts),
                "expected": len(batch_candidates),
                "title_matched": title_matched,
            }
            if valid_verdicts:
                return valid_verdicts, batch_diag
            if attempt + 1 < max_attempts:
                continue
            return [], batch_diag

        return [], {"batch": batch_idx, "parse_stage": "exhausted_attempts", "resolved": 0}

    all_verdicts: list[dict[str, Any]] = []
    resolved_ids: set[str] = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_verify_batch, i): i for i in range(len(prompts))}
        for future in concurrent.futures.as_completed(futures):
            try:
                verdicts, batch_diag = future.result()
                all_verdicts.extend(verdicts)
                for v in verdicts:
                    cid = v.get("candidate_id", "")
                    if cid:
                        resolved_ids.add(cid)
                diag["batch_results"].append(batch_diag)
                diag["total_resolved"] += len(verdicts)
                diag["raw_lengths"].append(batch_diag.get("raw_length", 0))
                diag["parse_stages"].append(batch_diag.get("parse_stage", "unknown"))
            except Exception as exc:
                logger.warning("verifier batch raised: %s", exc)
                diag["batch_results"].append({"batch": futures[future], "error": str(exc)})

    diag["coverage"] = diag["total_resolved"] / diag["total_input"] if diag["total_input"] > 0 else 1.0
    if diag["coverage"] < 1.0:
        all_candidate_ids = {c.get("candidate_id", "") for c in candidates}
        diag["unresolved_ids"] = sorted(all_candidate_ids - resolved_ids)
        diag["verification_status"] = "partial_coverage" if diag["coverage"] > 0 else "zero_coverage"
    else:
        diag["unresolved_ids"] = []
        diag["verification_status"] = "full_coverage"
    return all_verdicts, diag


def _normalise_verifier_output(out: Any) -> list[dict[str, Any]]:
    """Normalise verifier LLM output into list of dicts with candidate_id.

    Re7.6 hardened: handles reasoning wrappers, markdown fences, bytes,
    and nested object formats. Returns empty list only when truly no
    parseable verdicts exist.
    """
    if out is None:
        return []
    if isinstance(out, (int, float, bool)):
        return []
    if isinstance(out, bytes):
        try:
            out = out.decode("utf-8")
        except UnicodeDecodeError:
            return []
    if isinstance(out, dict):
        for key in ("verdicts", "verified", "candidates", "results", "items", "data"):
            cand = out.get(key)
            if isinstance(cand, list):
                items = [v for v in cand if isinstance(v, dict)]
                if items:
                    return items
        if "verdict" in out and "candidate_id" in out:
            return [out]
        if out and all(isinstance(v, str) for v in out.values()) and "candidate_id" in out:
            return [out]
        return []
    if isinstance(out, list):
        result = []
        for item in out:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                nested = _normalise_verifier_output(item)
                result.extend(nested)
        return result
    if isinstance(out, str):
        text = out.strip()
        if not text:
            return []
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            return _normalise_verifier_output(parsed)
        except json.JSONDecodeError:
            pass
        found = (re.search(r"\[.*\]", text, re.DOTALL)
                 or re.search(r"\{.*\}", text, re.DOTALL))
        if not found:
            return []
        try:
            parsed = json.loads(found.group(0))
            result = _normalise_verifier_output(parsed)
            if result:
                return result
        except json.JSONDecodeError:
            pass
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "[":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "]" and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        parsed = json.loads(text[start:i+1])
                        result = _normalise_verifier_output(parsed)
                        if result:
                            return result
                    except json.JSONDecodeError:
                        pass
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}" and depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        parsed = json.loads(text[start:i+1])
                        result = _normalise_verifier_output(parsed)
                        if result:
                            return result
                    except json.JSONDecodeError:
                        pass
        return []
    return []


def verify_node(state: ResearchState) -> dict[str, Any]:
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}

    verify_scope = state.get("verify_scope") or ""
    citation_done = state.get("citation_expansion_done", False)

    if verify_scope == "expanded":
        candidates = list(state.get("expanded_papers") or [])
    elif verify_scope == "repair":
        candidates = list(state.get("paper_candidates") or [])
    elif verify_scope == "search" or not citation_done:
        candidates = list(state.get("paper_candidates") or [])
    else:
        expanded = list(state.get("expanded_papers") or [])
        if expanded:
            candidates = expanded
        else:
            candidates = []

    user_constraints = state.get("user_constraints") or {}
    if isinstance(user_constraints, dict):
        verify_limit = int(user_constraints.get("max_verify_candidates", len(candidates)) or len(candidates))
        verify_limit = max(0, min(len(candidates), verify_limit))
        candidates = candidates[:verify_limit]

    # Re7.6: assign stable candidate_ids before sending to LLM
    candidates = _assign_candidate_ids(candidates)

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
    verification_diag: dict[str, Any] = {}
    verification_failed = False

    try:
        verdicts, verification_diag = _call_verifier(topic, atoms, candidates)

        # Build candidate_id → candidate index
        _candidate_by_id: dict[str, dict[str, Any]] = {}
        _candidate_by_title: dict[str, dict[str, Any]] = {}
        for c in candidates:
            cid = c.get("candidate_id", "")
            title = (c.get("title") or c.get("name") or "").strip().lower()
            if cid:
                _candidate_by_id[cid] = c
            if title:
                _candidate_by_title[title] = c

        keep = []
        weak = []
        rejected = []
        keep_ids: set[str] = set()

        for v in verdicts:
            cid = v.get("candidate_id", "")
            orig = _candidate_by_id.get(cid, {})
            if not orig:
                title = (v.get("title") or v.get("name") or "").strip()
                orig = _candidate_by_title.get(title.lower(), {})

            verdict = (v.get("verdict") or "").lower()
            item = {
                "title": orig.get("title") or v.get("title", ""),
                "candidate_id": cid or orig.get("candidate_id", ""),
                "verdict": verdict,
                "hit_keywords": v.get("hit_keywords") or [],
                "relation_to_topic": v.get("relation_to_topic") or "none",
                "reason": v.get("reason") or "",
                "doi": orig.get("doi") or v.get("doi"),
                "url": orig.get("url") or v.get("url"),
                "source": orig.get("source") or v.get("source"),
                "paper_id": orig.get("paper_id") or v.get("paper_id"),
                "arxiv_id": orig.get("arxiv_id") or v.get("arxiv_id"),
                "citation_count": orig.get("citation_count") or v.get("citation_count") or 0,
                "abstract": orig.get("abstract") or v.get("abstract") or "",
            }

            dedup_key = cid or (item.get("title") or "").lower().strip()
            if dedup_key and dedup_key in keep_ids:
                continue
            if dedup_key:
                keep_ids.add(dedup_key)

            if verdict == "accept":
                keep.append(item)
            elif verdict == "weak_reject":
                weak.append(item)
            else:
                rejected.append(item)

        # Re7.6: detect verification failure / partial coverage
        verification_status = verification_diag.get("verification_status", "zero_coverage")
        if not verdicts and len(candidates) > 0:
            verification_failed = True
            errors.append({
                "node": "verify",
                "error": "verification_failed",
                "detail": f"zero verdicts resolved for {len(candidates)} candidates",
                "diagnostics": verification_diag,
            })
        elif verification_status == "partial_coverage":
            unresolved_ids = verification_diag.get("unresolved_ids", [])
            errors.append({
                "node": "verify",
                "error": "partial_coverage",
                "detail": f"{len(unresolved_ids)}/{len(candidates)} candidates unresolved",
                "unresolved_ids": unresolved_ids[:50],
            })

        trace["output_summary"] = {
            "n_accept": len(keep),
            "n_weak_reject": len(weak),
            "n_reject": len(rejected),
            "n_input": len(candidates),
            "n_resolved": len(verdicts),
            "coverage": verification_diag.get("coverage", 0),
            "verification_failed": verification_failed,
            "verification_status": verification_status,
            "unresolved_ids": verification_diag.get("unresolved_ids", [])[:50],
            "invalid_ids": verification_diag.get("invalid_ids", [])[:50],
            "raw_lengths": verification_diag.get("raw_lengths", []),
            "parse_stages": verification_diag.get("parse_stages", []),
            "provider": verification_diag.get("provider", ""),
            "model": verification_diag.get("model", ""),
            "contract_id": verification_diag.get("contract_id", ""),
        }
    except Exception as exc:
        logger.exception("verify_node LLM call failed — candidates quarantined")
        verification_failed = True
        rejected_titles = [c.get("title") or c.get("name") or "" for c in candidates]
        errors.append({"node": "verify", "error": f"LLMUnavailable:{type(exc).__name__}"})
        trace["errors"].append({
            "phase": "llm_call", "error": f"{type(exc).__name__}",
            "action": "quarantine_all", "quarantined_titles": rejected_titles[:50],
        })
        trace["output_summary"] = {
            "n_accept": 0, "n_reject_or_weak": len(rejected_titles),
            "note": "verify_failed_all_quarantined", "verification_failed": True,
        }

    trace["ended_at"] = _now_iso()
    trace["elapsed_s"] = round(time.time() - t0, 3)

    # Re7.6: when verification failed, preserve candidates — don't silently drop
    if verification_failed and not keep and not weak:
        keep = [dict(c) for c in candidates]
        for item in keep:
            item["verdict"] = "unresolved"
            item["verification_status"] = "verification_failed"

    # Re7.6: partial coverage — mark unresolved candidates as "unresolved", not dropped
    if verification_status == "partial_coverage" and not verification_failed:
        resolved_cid_set = {v.get("candidate_id", "") for v in verdicts}
        for c in candidates:
            cid = c.get("candidate_id", "")
            if cid not in resolved_cid_set:
                item = dict(c)
                item["verdict"] = "unresolved"
                item["verification_status"] = "unresolved"
                keep.append(item)

    if citation_done:
        existing_verified = list(state.get("verified_papers") or [])
        existing_weak = list(state.get("weak_papers") or [])
        seen_titles: set[str] = set()
        for p in existing_verified + existing_weak:
            t = (p.get("title") or "").strip().lower()
            if t:
                seen_titles.add(t)
        deduped_verified = [p for p in keep if (p.get("title") or "").strip().lower() not in seen_titles]
        deduped_weak = [p for p in weak if (p.get("title") or "").strip().lower() not in seen_titles]
        return {
            "verified_papers": existing_verified + deduped_verified,
            "weak_papers": existing_weak + deduped_weak,
            "paper_candidates": candidates,
            "trace_events": [trace], "errors": errors,
            "provider_profile": "fast_json",
        }

    return {
        "verified_papers": keep,
        "weak_papers": weak,
        "paper_candidates": candidates,
        "trace_events": [trace],
        "errors": errors,
        "provider_profile": "fast_json",
    }
