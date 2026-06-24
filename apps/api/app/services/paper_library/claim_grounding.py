"""Session 48: Claim Grounding skill (SOP §5).

ground_claim(claim, project_id, scope, top_k) -> ClaimGroundingResult

流程:
  claim
    -> rewrite_query (复用 retriever.rewrite_query)
    -> retriever.retrieve (默认 scope=accepted_papers)
    -> reranker.rerank_chunks
    -> LLM 判定每 chunk 与 claim 的关系 (direct/indirect/background/contradiction)
       fallback: heuristic (关键词 overlap + 否定检测)

verdict (SOP §5.1):
  supported     -> 至少 1 个 direct/indirect
  weak_support  -> 仅有 background 或 score 0.4-0.7
  contradiction -> 存在 contradiction 且无 direct/indirect
  unsupported   -> 无命中或全 score < 0.4

引用规则 (Task 6) — 在 _classify_chunks 中执行:
  - rejected chunk: 不参与判定
  - pending chunk:  仅 background, 不可 direct/indirect
  - failed verify:  不可 direct/indirect
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...schemas_claim_grounding import ClaimGroundingResult
from ...schemas_paper_rag import EvidenceRef, SupportType
from .. import evidence as ev_store
from .. import llm
from . import reranker, retriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 否定词 (heuristic contradiction detection)
# ---------------------------------------------------------------------------

_NEGATION_PATTERNS = [
    r"\bnot\b", r"\bno\b", r"\bnever\b", r"\bfails?\b", r"\bcannot\b",
    r"\b不会\b", r"\b不能\b", r"\b无法\b", r"\b不\b", r"\b无\b", r"\b失败\b",
]


def _has_negation(text: str, claim_keywords: list[str]) -> bool:
    """粗略检测 chunk 是否在 claim 关键词上下文中表达否定.

    仅当 negation 与 claim 关键词在同一句 (间隔 ≤ 30 字) 才判 contradiction.
    """

    if not text or not claim_keywords:
        return False
    low = text.lower()
    for pat in _NEGATION_PATTERNS:
        for m in re.finditer(pat, low):
            start, end = m.span()
            window = low[max(0, start - 40): min(len(low), end + 40)]
            for kw in claim_keywords:
                if kw and kw.lower() in window:
                    return True
    return False


def _keyword_overlap(claim: str, text: str) -> float:
    """Jaccard-like: claim 关键词在 text 的命中率."""

    if not claim or not text:
        return 0.0
    from . import embedding

    c_tokens = set(embedding.tokenize(claim))
    t_tokens = set(embedding.tokenize(text))
    if not c_tokens or not t_tokens:
        return 0.0
    return len(c_tokens & t_tokens) / len(c_tokens)


def _heuristic_claim_keywords(claim: str) -> list[str]:
    """从 claim 抽关键词 (复用 retriever.rewrite_query 思路, 但不过度扩展)."""

    if not claim:
        return []
    keywords = retriever.rewrite_query(claim)
    # 仅保留长 ≥ 2 的, 避免单字干扰
    return [k for k in keywords if len(k) >= 2]


# ---------------------------------------------------------------------------
# 引用规则 — chunk 状态查询
# ---------------------------------------------------------------------------


def _chunk_status_in_ledger(
    project_id: str, paper_id: str, chunk_id: str,
) -> tuple[str, str]:
    """查 ledger 中 chunk 的 (review_status, verification_status).

    chunk 不在 ledger → 默认 ('pending', 'unverified') (RAG 刚产生还没写).
    """

    item = ev_store.find_paper_library_chunk(project_id, paper_id, chunk_id)
    if not item:
        return ("pending", "unverified")
    return (item.review_status or "pending", item.verification_status or "unverified")


def _enforce_citation_rules_on_ref(
    project_id: str, ref: EvidenceRef,
) -> EvidenceRef | None:
    """应用引用规则 (Task 6) 到单条 ref.

    Returns:
      - None: 该 ref 应被丢弃 (rejected)
      - ref (可能降级 support_type): 保留
    """

    rs, vs = _chunk_status_in_ledger(project_id, ref.paper_id, ref.chunk_id)
    if rs == "rejected":
        return None
    new_type = ref.support_type
    if rs == "pending" and new_type in ("direct", "indirect"):
        new_type = "background"
    if vs == "failed" and new_type in ("direct", "indirect"):
        new_type = "background"
    if new_type != ref.support_type:
        return ref.model_copy(update={"support_type": new_type})
    return ref


# ---------------------------------------------------------------------------
# Heuristic classify
# ---------------------------------------------------------------------------


def _heuristic_classify(
    project_id: str,
    claim: str,
    chunks: list[dict],
) -> tuple[list[EvidenceRef], list[EvidenceRef], list[EvidenceRef], float, str]:
    """Heuristic 判定: 返回 (supporting, contradicting, background, confidence, reason)."""

    if not chunks:
        return [], [], [], 0.0, "无命中 chunk"

    kws = _heuristic_claim_keywords(claim)
    supporting: list[EvidenceRef] = []
    contradicting: list[EvidenceRef] = []
    background: list[EvidenceRef] = []

    for c in chunks:
        cid = c.get("chunk_id", "")
        pid = c.get("paper_id", "")
        text = c.get("text", "") or ""
        score = float(c.get("rerank_score", 0.0) or 0.0)
        page_start = c.get("page_start")
        page_end = c.get("page_end")
        if not cid or not pid:
            continue
        ref = EvidenceRef(
            paper_id=pid, chunk_id=cid,
            page_start=page_start, page_end=page_end,
            quote=text[:200], support_type="indirect",
            score=score,
        )
        # 引用规则先过滤
        ref = _enforce_citation_rules_on_ref(project_id, ref)
        if ref is None:
            continue

        # contradiction 检测
        if _has_negation(text, kws):
            contradicting.append(ref.model_copy(update={"support_type": "contradiction"}))
            continue

        # 关键词 overlap → indirect
        overlap = _keyword_overlap(claim, text)
        if overlap >= 0.3 or score >= 0.7:
            new_type = "direct" if (overlap >= 0.5 or score >= 0.7) else "indirect"
            if ref.support_type in ("direct", "indirect"):
                new_type = ref.support_type
            supporting.append(ref.model_copy(update={"support_type": new_type}))
        else:
            background.append(ref.model_copy(update={"support_type": "background"}))

    # confidence: max score of supporting, fallback to background avg
    if supporting:
        conf = max(r.score for r in supporting)
    elif contradicting:
        conf = max(r.score for r in contradicting)
    elif background:
        conf = max(r.score for r in background) * 0.5
    else:
        conf = 0.0
    reason = (
        f"heuristic: supporting={len(supporting)} contradicting={len(contradicting)} "
        f"background={len(background)} confidence={conf:.2f}"
    )
    return supporting, contradicting, background, round(conf, 4), reason


# ---------------------------------------------------------------------------
# LLM classify
# ---------------------------------------------------------------------------


_LLM_PROMPT = """你是论文库 claim-grounding 判定器. 输入 1 个 claim + N 个候选 chunk.

对每个 chunk, 判断它与 claim 的关系:
  - direct:        chunk 直接陈述 claim
  - indirect:      chunk 间接支持 claim
  - background:    chunk 仅提供背景, 不直接支持
  - contradiction: chunk 与 claim 矛盾

严格返回 JSON (不带 markdown):
{{
  "classifications": [
    {{"ref_id": 1, "support_type": "direct|indirect|background|contradiction", "reason": "≤30 字"}},
    ...
  ],
  "verdict": "supported|weak_support|contradiction|unsupported",
  "confidence": 0.0-1.0,
  "reason": "≤80 字总评"
}}

claim: {claim}

chunks:
{chunks}
"""


def _llm_classify(
    claim: str,
    chunks: list[dict],
) -> tuple[dict[int, str], str, float, str] | None:
    """调 LLM 分类每 chunk, 返回 (chunk_idx→support_type, verdict, confidence, reason) 或 None."""

    if not chunks:
        return None
    # 拼 chunks (≤ 300 字截断)
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        text = (c.get("text", "") or "")[:300]
        page = f"p.{c.get('page_start')}" if c.get("page_start") else ""
        parts.append(f"[{i}] paper={c.get('paper_id', '?')} {page}\n{text}")
    chunks_block = "\n\n---\n\n".join(parts)
    prompt = _LLM_PROMPT.format(claim=claim, chunks=chunks_block)
    try:
        raw = llm.chat_json(prompt, temperature=0.1, max_tokens=1200, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM claim-grounding failed: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    classifications_raw = raw.get("classifications") or []
    idx_to_type: dict[int, str] = {}
    for c in classifications_raw:
        if not isinstance(c, dict):
            continue
        try:
            ridx = int(c.get("ref_id"))
        except (TypeError, ValueError):
            continue
        st = c.get("support_type", "background")
        if st not in ("direct", "indirect", "background", "contradiction"):
            st = "background"
        idx_to_type[ridx] = st
    verdict = raw.get("verdict", "unsupported")
    if verdict not in ("supported", "weak_support", "contradiction", "unsupported"):
        verdict = "unsupported"
    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reason = str(raw.get("reason", ""))[:200]
    return idx_to_type, verdict, confidence, reason


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _to_status(verdict: str) -> str:
    """verdict → status (alias 字段)."""

    if verdict not in ("supported", "weak_support", "contradiction", "unsupported"):
        return "unsupported"
    return verdict


def _assemble_result(
    claim: str,
    mode: str,
    chunks: list[dict],
    idx_to_type: dict[int, str] | None,
    verdict: str,
    confidence: float,
    reason: str,
    project_id: str,
) -> ClaimGroundingResult:
    """把 LLM 或 heuristic 输出组装成 ClaimGroundingResult (含引用规则)."""

    supporting: list[EvidenceRef] = []
    contradicting: list[EvidenceRef] = []
    background: list[EvidenceRef] = []

    for i, c in enumerate(chunks, start=1):
        cid = c.get("chunk_id", "")
        pid = c.get("paper_id", "")
        text = c.get("text", "") or ""
        score = float(c.get("rerank_score", 0.0) or 0.0)
        page_start = c.get("page_start")
        page_end = c.get("page_end")
        if not cid or not pid:
            continue

        # LLM 路径: idx_to_type[i] 给分类; heuristic 路径: idx_to_type=None 用 classify 重跑
        if idx_to_type is not None:
            st = idx_to_type.get(i, "background")
        else:
            # heuristic 路径: 调用 _heuristic_classify 的单 chunk 简化版
            kws = _heuristic_claim_keywords(claim)
            overlap = _keyword_overlap(claim, text)
            if _has_negation(text, kws):
                st = "contradiction"
            elif overlap >= 0.5 or score >= 0.7:
                st = "direct"
            elif overlap >= 0.3 or score >= 0.5:
                st = "indirect"
            else:
                st = "background"

        ref = EvidenceRef(
            paper_id=pid, chunk_id=cid,
            page_start=page_start, page_end=page_end,
            quote=text[:200], support_type=st,  # type: ignore[arg-type]
            score=score,
        )
        # 引用规则: rejected 永不返回
        ref = _enforce_citation_rules_on_ref(project_id, ref)
        if ref is None:
            continue

        if ref.support_type in ("direct", "indirect"):
            supporting.append(ref)
        elif ref.support_type == "contradiction":
            contradicting.append(ref)
        else:
            background.append(ref)

    # 重新推导 verdict (引用规则可能清空 supporting)
    if supporting:
        final_verdict = "supported"
    elif contradicting:
        final_verdict = "contradiction"
    elif background and max((r.score for r in background), default=0.0) >= 0.4:
        final_verdict = "weak_support"
    else:
        final_verdict = "unsupported"

    return ClaimGroundingResult(
        claim=claim,
        status=_to_status(final_verdict),
        verdict=final_verdict,
        confidence=round(confidence, 4),
        supporting_chunks=supporting[:5],
        contradicting_chunks=contradicting[:5],
        background_chunks=background[:5],
        reason=reason or f"{mode} path: {final_verdict}",
        retrieval_mode=mode,  # type: ignore[arg-type]
    )


def ground_claim(
    claim: str,
    project_id: str,
    scope: str = "accepted_papers",
    paper_ids: list[str] | None = None,
    top_k: int = 5,
) -> ClaimGroundingResult:
    """主入口: 输入报告断言, 返回 ClaimGroundingResult.

    流程: retriever.retrieve → reranker.rerank_chunks → LLM 判定 → 引用规则强制.
    """

    if not claim or not claim.strip():
        return ClaimGroundingResult(
            claim=claim or "", status="unsupported", verdict="unsupported",
            confidence=0.0, reason="claim 为空",
            retrieval_mode="fallback",
        )

    # 1) 检索
    try:
        hits = retriever.retrieve(
            project_id=project_id,
            question=claim,
            scope=scope,  # type: ignore[arg-type]
            paper_ids=paper_ids,
            top_k=top_k,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("claim_grounding retrieve failed: %s", exc)
        return ClaimGroundingResult(
            claim=claim, status="unsupported", verdict="unsupported",
            confidence=0.0, reason=f"retrieval failed: {exc}",
            retrieval_mode="fallback",
        )

    if not hits:
        return ClaimGroundingResult(
            claim=claim, status="unsupported", verdict="unsupported",
            confidence=0.0, reason="未在论文库中找到证据",
            retrieval_mode="fallback",
        )

    # 2) 还原 chunk 元数据
    from . import indexer
    idx = indexer.load_index(project_id)
    chunks_index = idx.get("chunks", {})
    raw_chunks: list[dict] = []
    for cid, _ in hits:
        meta = chunks_index.get(cid)
        if not meta:
            continue
        meta = dict(meta)
        meta["chunk_id"] = cid
        raw_chunks.append(meta)

    if not raw_chunks:
        return ClaimGroundingResult(
            claim=claim, status="unsupported", verdict="unsupported",
            confidence=0.0, reason="chunk 元数据缺失",
            retrieval_mode="fallback",
        )

    # 3) rerank
    reranked = reranker.rerank_chunks(claim, [(m, 0.0) for m in raw_chunks])
    top_chunks = [m for m, _ in reranked[:top_k]]

    # 4) LLM 分类 (失败 → heuristic)
    llm_out = _llm_classify(claim, top_chunks)
    if llm_out is not None:
        idx_to_type, verdict, confidence, reason = llm_out
        return _assemble_result(
            claim=claim, mode="llm", chunks=top_chunks,
            idx_to_type=idx_to_type, verdict=verdict,
            confidence=confidence, reason=reason, project_id=project_id,
        )

    # 5) Heuristic fallback
    supporting, contradicting, background, confidence, reason = _heuristic_classify(
        project_id, claim, top_chunks,
    )
    if supporting:
        verdict = "supported"
    elif contradicting:
        verdict = "contradiction"
    elif background and max((r.score for r in background), default=0.0) >= 0.4:
        verdict = "weak_support"
    else:
        verdict = "unsupported"

    # 直接组装, 不再走 _assemble_result 的二次判定 (heuristic 已经分好类)
    return ClaimGroundingResult(
        claim=claim,
        status=_to_status(verdict),
        verdict=verdict,
        confidence=round(confidence, 4),
        supporting_chunks=supporting[:5],
        contradicting_chunks=contradicting[:5],
        background_chunks=background[:5],
        reason=reason,
        retrieval_mode="fallback",
    )


__all__ = [
    "ground_claim",
]