"""LangGraph node: verify paper candidates against the topic.

Uses the llm_router (fast_json profile) to apply re11_paper_verifier prompt;
produces verified_papers with per-keyword breakdown and drops rejected entries
into trace for auditability.
"""
from __future__ import annotations

import logging
import os
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


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _call_verifier(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verify candidates against topic using parallel LLM calls.

    Each candidate is sent as an independent parallel request via
    ThreadPoolExecutor; this reduces wall-clock time from ~24×18s (sequential)
    to ~20-30s (parallel, limited by slowest call plus fallback overhead).

    Reasoner models (stepfun step-3.7-flash) put the JSON payload in
    ``reasoning`` rather than ``content``; ``call_json`` handles 3-phase repair
    internally, so this function only needs to drive parallelism + normalise.
    """
    import concurrent.futures

    from apps.api.app.services import llm_router
    from apps.api.app.services.agents.prompts import re11_paper_verifier as P

    if not candidates:
        return []

    max_workers = max(1, min(len(candidates), _env_int("VERIFIER_MAX_WORKERS", 2)))
    timeout_s = max(5, _env_int("VERIFIER_TIMEOUT_S", 120))

    max_attempts = max(1, _env_int("VERIFIER_MAX_ATTEMPTS", 2))

    def _verify_one(candidate: dict[str, Any]) -> list[dict[str, Any]]:
        """Verify a single candidate; returns list of normalised verdict dicts."""
        last_exc: BaseException | None = None
        for attempt in range(max_attempts):
            try:
                built = P.build_one(topic, atoms, candidate)
                out = llm_router.call_json(
                    built["user"],
                    system=built["system"],
                    profile="fast_json",
                    max_tokens=1200,
                    timeout=timeout_s,
                    expected="dict",
                    schema_hint='Top-level object with keys: title, verdict, hit_keywords, relation_to_topic, reason',
                )
                verdicts = _normalise_verifier_output(out)
                if not verdicts and attempt + 1 < max_attempts:
                    continue
                return verdicts
            except BaseException as exc:
                last_exc = exc
                logger.debug("verifier attempt %s failed for %r: %s",
                             attempt, candidate.get("title", "??"), type(exc).__name__)
        if last_exc is not None:
            logger.warning("verifier final failure for %r: %s",
                           candidate.get("title", "??"), type(last_exc).__name__)
        return []

    all_verdicts: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_verify_one, c): c for c in candidates}
        for future in concurrent.futures.as_completed(futures):
            try:
                verdicts = future.result()
                all_verdicts.extend(verdicts)
            except BaseException as exc:
                cand = futures[future]
                logger.warning("verifier future raised for %r: %s",
                               cand.get("title", "??"), exc)

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
    candidates = list(state.get("paper_candidates") or [])
    user_constraints = state.get("user_constraints") or {}
    if isinstance(user_constraints, dict):
        verify_limit = int(user_constraints.get("max_verify_candidates", len(candidates)) or len(candidates))
        verify_limit = max(0, min(len(candidates), verify_limit))
        candidates = candidates[:verify_limit]
    t0 = time.time()

    trace: dict[str, Any] = {
        "node": "verify",
        "started_at": _now_iso(),
        "input_summary": {"n_candidates": len(candidates), "topic_len": len(topic)},
        "output_summary": {},
        "tool_calls": [{"tool": "re11_paper_verifier.llm", "profile": "fast_json"}],
        "errors": [],
        "provider": "fast_json",
    }
    errors: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    try:
        verdicts = _call_verifier(topic, atoms, candidates)
        # Map loose schema to normalized candidate.
        keep = []
        rejected = []
        for v in verdicts:
            title = (v.get("title") or v.get("name") or "").strip()
            if not title:
                continue
            verdict = (v.get("verdict") or "").lower()
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
            }
            if verdict == "accept":
                keep.append(item)
            else:
                rejected.append(item)
        verified = keep
        trace["output_summary"] = {
            "n_accept": len(keep),
            "n_reject_or_weak": len(rejected),
        }
    except BaseException as exc:
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

    return {
        "verified_papers": verified,
        "paper_candidates": candidates,
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors,
        "provider_profile": "fast_json",
    }
