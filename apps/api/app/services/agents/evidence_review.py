"""EvidenceReview — light-weight LLM audit (Re02 Task 4).

For every candidate in the pool we emit one `EvidenceReview` row:

    candidate_id, evidence_type, role_hint, status (core | candidate |
    needs_manual | rejected), matched_terms, missing_terms,
    confidence_label (high | medium | low | unknown), relation_to_topic
    (baseline | parallel | module | dataset | repo | survey | background |
    weak_related | unrelated), exists_verdict (exists | likely_exists |
    not_found | metadata_mismatch), rank_reason, reason.

The LLM is given the FULL pool + parsed topic + source ledger + raw tool
output once, and returns one batched JSON list. We never call the LLM
once per candidate — that would burn the budget on bushy pools.

Per S66v rules: NO `*_score` fields. The only numerics are tier
enums; ranking is a side-effect of the order the LLM returns rows.

Re04-fix SOP §4: when the candidate pool is dominated by Chinese titles
(Case 027 raw_topic is pure Chinese), the English prompt + chunked call
returns malformed JSON. We (a) detect Chinese-dominant chunks, (b) drop
to a smaller chunk + the Chinese prompt RE04_EVIDENCE_REVIEW_SYSTEM, and
(c) if 2 retries still fail, fall back to a per-candidate evaluation
(chunk_size=1) which gives us a much higher chance of a successful LLM
JSON response because each call carries one row.

Ponytail: dataclass + 1 LLM call wrapper + 1 heuristic fallback. ~150 lines.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLMUnavailable
from .prompts import (
    EVIDENCE_REVIEW_SYSTEM,
    RE04_EVIDENCE_REVIEW_SYSTEM,
    USER_TEMPLATE_EVIDENCE_REVIEW,
)

logger = logging.getLogger(__name__)


# Re04-fix SOP §4: Chinese-character detection for chunk routing.
_CHINESE_CHAR_RE = re.compile(r"[一-鿿]")
_CANDIDATE_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')


VALID_STATUS = {"core", "candidate", "needs_manual", "rejected"}
VALID_RELATION = {
    "baseline", "parallel", "module", "dataset", "repo",
    "survey", "background", "weak_related", "unrelated",
}
VALID_EXISTS = {"exists", "likely_exists", "not_found", "metadata_mismatch"}
VALID_CONFIDENCE = {"high", "medium", "low", "unknown"}
VALID_EVIDENCE_TYPE = {"paper", "dataset", "repo", "survey", "unknown"}
VALID_ROLE_HINT = {
    "baseline", "parallel", "module", "reference", "dataset", "repo",
    "needs_manual", "unknown",
}


@dataclass
class EvidenceReview:
    candidate_id: str
    evidence_type: str = "unknown"
    role_hint: str = "unknown"
    status: str = "candidate"
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    confidence_label: str = "unknown"
    relation_to_topic: str = "weak_related"
    exists_verdict: str = "likely_exists"
    rank_reason: str = ""
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "evidence_type": self.evidence_type,
            "role_hint": self.role_hint,
            "status": self.status,
            "matched_terms": list(self.matched_terms),
            "missing_terms": list(self.missing_terms),
            "confidence_label": self.confidence_label,
            "relation_to_topic": self.relation_to_topic,
            "exists_verdict": self.exists_verdict,
            "rank_reason": self.rank_reason,
            "reason": self.reason,
        }


def _has_majority_chinese(chunk: list[dict[str, Any]], threshold: float = 0.5) -> bool:
    """Return True if >threshold of candidates in `chunk` have a Chinese title.

    Re04-fix SOP §4.A: detect Chinese-dominant chunks so we can route them
    to the Chinese-language RE04_EVIDENCE_REVIEW_SYSTEM prompt with a
    smaller chunk size. The detection is purely structural — we never
    leak the LLM any verdict info.
    """
    if not chunk:
        return False
    n_zh = 0
    n_total = 0
    for c in chunk:
        title = (c.get("title") or "").strip()
        if not title:
            continue
        n_total += 1
        if _CHINESE_CHAR_RE.search(title):
            n_zh += 1
    if n_total == 0:
        return False
    return (n_zh / n_total) > threshold


def _normalize_review(raw: dict[str, Any], fallback_id: str) -> EvidenceReview:
    cid = str(raw.get("candidate_id") or fallback_id)
    def _in(enum: set[str], key: str, default: str) -> str:
        v = str(raw.get(key) or default).strip().lower()
        return v if v in enum else default
    matched = raw.get("matched_terms") or []
    missing = raw.get("missing_terms") or []
    return EvidenceReview(
        candidate_id=cid,
        evidence_type=_in(VALID_EVIDENCE_TYPE, "evidence_type", "unknown"),
        role_hint=_in(VALID_ROLE_HINT, "role_hint", "unknown"),
        status=_in(VALID_STATUS, "status", "candidate"),
        matched_terms=[str(m) for m in matched][:8] if isinstance(matched, list) else [],
        missing_terms=[str(m) for m in missing][:8] if isinstance(missing, list) else [],
        confidence_label=_in(VALID_CONFIDENCE, "confidence_label", "unknown"),
        relation_to_topic=_in(VALID_RELATION, "relation_to_topic", "weak_related"),
        exists_verdict=_in(VALID_EXISTS, "exists_verdict", "likely_exists"),
        rank_reason=str(raw.get("rank_reason") or "")[:200],
        reason=str(raw.get("reason") or "")[:400],
    )


def audit_candidates(
    *,
    parsed_topic: dict,
    candidates: list[dict[str, Any]],
    raw: dict[str, list[dict[str, Any]]] | None = None,
    chat_json_strict,
) -> list[EvidenceReview]:
    """Re03 chunked audit (SOP §4). 1 LLM call per chunk of CHUNK_SIZE
    candidates. Returns list[EvidenceReview] keyed by candidate_id.

    Each chunk's LLM call is retried once with 2× max_tokens on JSON
    parse failure. If a chunk still fails, the affected candidates get
    a heuristic `candidate` tier + an `llm_blocker: evidence_review_parse_failed`
    marker on their EvidenceReview.reason (or via a separate block).
    Downstream Low-bar reads `llm_blocker` to refuse `pass` when present.

    Re04-fix SOP §4: when the chunk's titles are >50% Chinese, we route
    to RE04_EVIDENCE_REVIEW_SYSTEM with chunk_size halved. If 2 retries
    on the full chunk still fail, we drop to chunk_size=1 per-candidate
    evaluation (3rd-tier fallback) — much higher success rate because
    each call carries a tiny payload.
    """
    if not candidates:
        return []

    base_chunk_size = int(os.environ.get("PAPERAGENT_ER_CHUNK_SIZE", "20"))
    chunks = [candidates[i:i + base_chunk_size] for i in range(0, len(candidates), base_chunk_size)]
    all_reviews: list[EvidenceReview] = []
    blocked_ids: set[str] = set()
    failed_chunks: list[list[dict[str, Any]]] = []  # chunks that failed both retries
    chunk_stats: list[dict[str, Any]] = []

    raw = raw or {}
    raw_block = json.dumps(
        {a: [{"title": (it.get("title") or "")[:120],
              "url": it.get("url") or it.get("html_url") or "",
              "year": it.get("year") or it.get("publication_year")}
             for it in (raw.get(a) or [])[:8]]
         for a in ("arxiv", "openalex", "crossref", "github")},
        ensure_ascii=False,
    )

    for chunk_idx, chunk in enumerate(chunks):
        # Re04-fix SOP §4.B: route Chinese-dominant chunks to the
        # Chinese prompt with a smaller chunk size.
        if _has_majority_chinese(chunk):
            zh_sub_size = max(2, base_chunk_size // 2)
            sub_chunks = [chunk[i:i + zh_sub_size] for i in range(0, len(chunk), zh_sub_size)]
            for sub in sub_chunks:
                block, stats = _audit_one_chunk(
                    chunk=sub,
                    parsed_topic=parsed_topic,
                    raw_block=raw_block,
                    chat_json_strict=chat_json_strict,
                    system_prompt=RE04_EVIDENCE_REVIEW_SYSTEM,
                )
                chunk_stats.append({**stats, "chinese_routed": True})
                for r in block["reviews"]:
                    all_reviews.append(r)
                blocked_ids.update(block["blocked_ids"])
                if not stats.get("success"):
                    failed_chunks.append(sub)
        else:
            block, stats = _audit_one_chunk(
                chunk=chunk,
                parsed_topic=parsed_topic,
                raw_block=raw_block,
                chat_json_strict=chat_json_strict,
            )
            chunk_stats.append({**stats, "chinese_routed": False})
            for r in block["reviews"]:
                all_reviews.append(r)
            blocked_ids.update(block["blocked_ids"])
            if not stats.get("success"):
                failed_chunks.append(chunk)

    # Re04-fix SOP §4.C: 3rd-tier fallback — per-candidate evaluation
    # for any chunk that survived 2 retries with broken JSON. Each
    # candidate gets its own call so the LLM only needs to return one
    # row of JSON, drastically increasing success rate.
    per_candidate_success: set[str] = set()
    if failed_chunks:
        for fc in failed_chunks:
            for c in fc:
                block, stats = _audit_one_chunk(
                    chunk=[c],
                    parsed_topic=parsed_topic,
                    raw_block=raw_block,
                    chat_json_strict=chat_json_strict,
                    system_prompt=(
                        RE04_EVIDENCE_REVIEW_SYSTEM
                        if _has_majority_chinese([c]) else None
                    ),
                )
                chunk_stats.append({**stats, "per_candidate_fallback": True})
                # Replace the heuristic review for this candidate with the
                # successful LLM row, if any. Track success for marker.
                returned_rows = [
                    r for r in block["reviews"]
                    if r.candidate_id == c["candidate_id"] and r.status != "candidate"
                ]
                # Even if status==candidate, if LLM responded it's better
                # than the bare heuristic, so we accept any non-empty return.
                if stats.get("success") and block["reviews"]:
                    per_candidate_success.add(c["candidate_id"])
                    # Remove old heuristic review for this candidate.
                    all_reviews = [
                        r for r in all_reviews if r.candidate_id != c["candidate_id"]
                    ]
                    for r in block["reviews"]:
                        all_reviews.append(r)
                    # This candidate is no longer "blocked".
                    blocked_ids.discard(c["candidate_id"])

    # Any candidate not returned by LLM in any chunk → heuristic-default
    returned = {r.candidate_id for r in all_reviews}
    for c in candidates:
        if c["candidate_id"] not in returned:
            all_reviews.append(_heuristic_review_for(c))
            # Candidates that weren't returned by LLM are also marked
            # blocked (heuristic default without LLM verdict).
            blocked_ids.add(c["candidate_id"])
    # Apply blocker suffix to all blocked reviews
    for r in all_reviews:
        if r.candidate_id in blocked_ids:
            # Re04-fix SOP §4.D: distinguish the per-candidate fallback
            # outcomes with specific markers.
            if r.candidate_id in per_candidate_success:
                # Successful per-candidate fallback — shouldn't normally
                # land here since success removes the id from blocked_ids,
                # but be defensive.
                tag = "[degraded: chunk_fallback_per_candidate]"
            elif any(c["candidate_id"] == r.candidate_id for fc in failed_chunks for c in fc):
                tag = "[degraded: chunk_fallback_per_candidate_failed]"
            else:
                tag = "[llm_blocker: evidence_review_parse_failed]"
            if tag not in r.reason:
                r.reason = (r.reason or "")[:200] + " " + tag
                r.reason = r.reason[:400]

    return all_reviews


def _audit_one_chunk(
    *,
    chunk: list[dict[str, Any]],
    parsed_topic: dict,
    raw_block: str,
    chat_json_strict,
    system_prompt: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """One chunk's LLM call. Returns {reviews, blocked_ids} + stats.

    blocked_ids: candidates whose LLM call failed; the orchestrator will
    tag them with `llm_blocker: evidence_review_parse_failed`.

    Re04-fix SOP §4: caller may override `system_prompt` (e.g. when
    `_has_majority_chinese(chunk)` is True, swap in RE04_EVIDENCE_REVIEW_SYSTEM).
    Default: English EVIDENCE_REVIEW_SYSTEM.
    """
    pool_block = json.dumps(
        # Re05 §4.2: expose a passive `is_dataset_candidate` flag on
        # dataset-evidence rows so the LLM can naturally elevate them
        # into the `dataset` relation_to_topic bucket. SOP forbids any
        # hard rule in the prompt that ties this flag to relation, so
        # the field is purely informational — the LLM sees it, decides.
        [
            {
                "candidate_id": c["candidate_id"],
                "evidence_type": c.get("evidence_type"),
                "role_hint": c.get("role_hint"),
                "title": c.get("title"),
                "year": c.get("year"),
                "venue": c.get("venue"),
                "description": (c.get("description") or "")[:240],
                "abstract": (c.get("abstract") or "")[:240],
                "sources": c.get("sources") or [],
                "is_dataset_candidate": (
                    (c.get("evidence_type") == "dataset")
                    or (c.get("role_hint") == "dataset")
                ),
            }
            for c in chunk
        ],
        ensure_ascii=False,
    )

    prompt = USER_TEMPLATE_EVIDENCE_REVIEW.format(
        parsed_topic=json.dumps(parsed_topic, ensure_ascii=False),
        candidates_block=pool_block,
        raw_block=raw_block,
    )

    sys_prompt = system_prompt or EVIDENCE_REVIEW_SYSTEM

    base_max = int(os.environ.get("PAPERAGENT_ER_MAX_TOKENS", "12000"))
    base_timeout = 180.0
    reviews: list[EvidenceReview] = []
    blocked: set[str] = set()
    success = False
    last_error = ""

    for attempt, (max_t, timeout) in enumerate(
        [(base_max, base_timeout), (base_max * 2, base_timeout + 60.0)]
    ):
        try:
            out = chat_json_strict(prompt, sys_prompt, max_tokens=max_t, timeout=timeout)
            reviews_raw = out.get("reviews") or []
            if not isinstance(reviews_raw, list):
                raise LLMUnavailable("non-list reviews in response")
            by_id = {c["candidate_id"]: c for c in chunk}
            for row in reviews_raw:
                if not isinstance(row, dict):
                    continue
                cid = str(row.get("candidate_id") or "")
                if cid not in by_id:
                    continue
                reviews.append(_normalize_review(row, cid))
            success = True
            break
        except LLMUnavailable as exc:
            last_error = str(exc) or "LLMUnavailable"
            logger.warning("EvidenceReview chunk attempt %d failed: %s", attempt, last_error)
        except Exception as exc:  # noqa: BLE001
            # LLM returned bad JSON; try once more with 2x tokens
            last_error = str(exc) or "Exception"
            logger.warning("EvidenceReview chunk attempt %d JSON parse: %s", attempt, last_error)

    if not success:
        # Chunk failed — heuristic fallback, mark blocked
        for c in chunk:
            blocked.add(c["candidate_id"])
        # Return heuristic reviews (no LLM data)
        for c in chunk:
            reviews.append(_heuristic_review_for(c))
        stats = {"chunk_size": len(chunk), "success": False, "last_error": last_error}
        return ({"reviews": reviews, "blocked_ids": blocked}, stats)

    stats = {"chunk_size": len(chunk), "success": True, "last_error": ""}
    return ({"reviews": reviews, "blocked_ids": blocked}, stats)


def _heuristic_review_for(c: dict[str, Any]) -> EvidenceReview:
    """Default tier for an unreviewed candidate: 'candidate' (NOT rejected)."""
    return EvidenceReview(
        candidate_id=c["candidate_id"],
        evidence_type=str(c.get("evidence_type") or "unknown"),
        role_hint=str(c.get("role_hint") or "unknown"),
        status="candidate",
        confidence_label="unknown",
        relation_to_topic="weak_related",
        exists_verdict="likely_exists",
        rank_reason="heursitic-default: candidate present in pool, LLM did not return row",
        reason="auto-defaulted to candidate tier; manual review may upgrade or downgrade",
    )


def _heuristic_audit(candidates: list[dict[str, Any]]) -> list[EvidenceReview]:
    return [_heuristic_review_for(c) for c in candidates]


def index_by_candidate(reviews: list[EvidenceReview]) -> dict[str, EvidenceReview]:
    return {r.candidate_id: r for r in reviews}


def by_status(reviews: list[EvidenceReview]) -> dict[str, list[EvidenceReview]]:
    out: dict[str, list[EvidenceReview]] = {s: [] for s in VALID_STATUS}
    for r in reviews:
        out.setdefault(r.status, []).append(r)
    return out


def stats(reviews: list[EvidenceReview]) -> dict[str, int]:
    s = {k: 0 for k in VALID_STATUS}
    for r in reviews:
        s[r.status] = s.get(r.status, 0) + 1
    return s
