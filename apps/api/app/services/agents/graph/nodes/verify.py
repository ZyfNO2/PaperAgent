"""LangGraph node: verify paper candidates against the topic.

Uses the llm_router (fast_json profile) to apply re11_paper_verifier prompt;
produces verified_papers with per-keyword breakdown and drops rejected entries
into trace for auditability.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _call_verifier(topic: str, atoms: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from apps.api.app.services import llm_router
    from apps.api.app.services.agents.prompts import re11_paper_verifier as P

    # StepFun step-3.7-flash is a reasoning model: it thinks out loud in a
    # `reasoning` field and puts the clean JSON in `content`. We need a big
    # max_tokens budget so the LLM can both think (often 1-2k tokens) and
    # emit the JSON payload. Batch the candidates so each JSON response stays
    # within a reasonable size and never truncates mid-object.
    BATCH = 10
    all_verdicts: list[dict[str, Any]] = []
    for i in range(0, len(candidates), BATCH):
        chunk = candidates[i:i + BATCH]
        last_exc: BaseException | None = None
        for attempt in range(2):
            try:
                built = P.build(topic, atoms, chunk)
                out = llm_router.call_json(
                    built["user"],
                    system=built["system"],
                    profile="fast_json",
                    # reasoning (~2k tokens) + JSON (~150 per candidate, ~50 overhead)
                    max_tokens=min(8000, 3000 + len(chunk) * 200),
                    timeout=120,
                )
                # `out` may already be a parsed object from llm_router.call_json;
                # only scan raw text when it is still a string.
                scanned: list = (
                    [] if isinstance(out, (list, dict))
                    else llm_router.extract_json_objects(out)
                ) if hasattr(llm_router, "extract_json_objects") else []
                verified = (
                    out if isinstance(out, list) else None
                ) or out.get("verified") or out.get("candidates") or (
                    next((x for x in scanned if isinstance(x, list)), None)
                ) or []
                if isinstance(verified, dict):
                    for k, v in verified.items():
                        if isinstance(v, list):
                            all_verdicts.extend(v)
                            break
                    else:
                        all_verdicts.append(verified)
                elif isinstance(verified, list):
                    all_verdicts.extend(verified)
                last_exc = None
                break
            except BaseException as exc:  # noqa: BLE001
                last_exc = exc
        if last_exc is not None:
            raise last_exc
    return all_verdicts


def verify_node(state: ResearchState) -> dict[str, Any]:
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    candidates = state.get("paper_candidates") or []
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
