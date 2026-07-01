"""Session 47: Paper QA — LLM 问答 + fallback (SOP §8 + §11 Task 6).

build_context: 拼 chunks 为 LLM context
answer_with_llm: 调 services/llm.chat_json, 解析 evidence_refs/unsupported_claims
fallback_answer: LLM 失败时返回纯检索结果
compute_confidence: supported_claim_count / total_claim_count (heuristic)
write_answer_to_ledger: Session 48 Task 2 — 把 answer.evidence_refs 写入 Evidence Ledger
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ...schemas_paper_rag import EvidenceRef, PaperRAGAnswer, RetrievalMode, SupportType
from .. import evidence as ev_store
from .. import llm
from . import storage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# build_context
# ---------------------------------------------------------------------------


def build_context(
    chunks: list[dict],
    paper_titles: dict[str, str] | None = None,
) -> str:
    """把 chunks 拼成 LLM context.

    chunks: [{chunk_id, paper_id, section_title, text, page_start, ...}]
    """

    if not chunks:
        return ""
    paper_titles = paper_titles or {}
    parts: list[str] = []
    for i, c in enumerate(chunks, start=1):
        pid = c.get("paper_id", "?")
        title = paper_titles.get(pid, pid)
        section = c.get("section_title", "") or "Body"
        page = ""
        if c.get("page_start") is not None:
            page = f" (p.{c['page_start']})"
        text = (c.get("text", "") or "")[:1500]  # 截断
        parts.append(
            f"[{i}] paper={pid} title={title!r} section={section}{page}\n{text}"
        )
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# answer_with_llm
# ---------------------------------------------------------------------------


_PROMPT_TEMPLATE = """你是论文库助手。基于以下论文片段回答用户问题。

约束:
1. 每个断言必须能回溯到一个或多个片段 (引用编号 [1], [2] 等).
2. 无法从片段得出的内容, 列入 unsupported_claims, 不要编造.
3. quote 必须是 ≤ 200 字的原文片段.

论文片段:
{context}

用户问题: {question}

返回 JSON (严格, 不带 ```json ``` 标记):
{{
  "answer": "综合回答 (含 [1][2] 引用)",
  "evidence_refs": [
    {{"ref_id": 1, "paper_id": "...", "chunk_id": "...", "page_start": <int|null>, "page_end": <int|null>, "quote": "...", "support_type": "direct|indirect|background|contradiction"}}
  ],
  "unsupported_claims": ["...无法从片段得出的断言..."]
}}
"""


def answer_with_llm(
    question: str,
    chunks: list[dict],
    paper_titles: dict[str, str] | None = None,
) -> PaperRAGAnswer:
    """调 LLM 生成 answer + evidence_refs.

    失败: 抛 LLMUnavailable, 由上层 fallback.
    """

    if not chunks:
        return _no_hit_answer(question)

    context = build_context(chunks, paper_titles=paper_titles)
    prompt = _PROMPT_TEMPLATE.format(context=context, question=question)

    try:
        raw = llm.chat_json(prompt, temperature=0.2, max_tokens=1500, timeout=30.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM call failed: %s", exc)
        raise

    return _parse_llm_response(question, chunks, raw)


def _parse_llm_response(
    question: str,
    chunks: list[dict],
    raw: dict[str, Any],
) -> PaperRAGAnswer:
    """解析 LLM JSON 输出 → PaperRAGAnswer."""

    answer_text = (raw.get("answer") or "").strip()
    raw_refs = raw.get("evidence_refs") or []
    unsupported = raw.get("unsupported_claims") or []

    # ref_id → chunk 映射
    chunk_by_idx: dict[int, dict] = {i + 1: c for i, c in enumerate(chunks)}

    refs: list[EvidenceRef] = []
    valid_refs = 0
    for r in raw_refs:
        if not isinstance(r, dict):
            continue
        ref_id = r.get("ref_id")
        if ref_id is None:
            continue
        try:
            ref_idx = int(ref_id)
        except (TypeError, ValueError):
            continue
        chunk = chunk_by_idx.get(ref_idx)
        if not chunk:
            # LLM 引用了不存在的 ref → 视为 unsupported
            unsupported.append(
                f"LLM 引用了 [#{ref_id}] 但不在片段中: "
                f"{str(r.get('quote', ''))[:80]}"
            )
            continue
        valid_refs += 1
        quote = (r.get("quote") or "").strip()[:200]
        if not quote:
            quote = (chunk.get("text", "") or "")[:200]
        try:
            support_t: SupportType = r.get("support_type", "direct")
            if support_t not in ("direct", "indirect", "background", "contradiction"):
                support_t = "direct"
        except Exception:  # noqa: BLE001
            support_t = "direct"
        page_start = r.get("page_start") or chunk.get("page_start")
        page_end = r.get("page_end") or chunk.get("page_end")
        try:
            page_start = int(page_start) if page_start is not None else None
        except (TypeError, ValueError):
            page_start = None
        try:
            page_end = int(page_end) if page_end is not None else None
        except (TypeError, ValueError):
            page_end = None
        refs.append(EvidenceRef(
            paper_id=chunk.get("paper_id", ""),
            chunk_id=chunk.get("chunk_id", ""),
            page_start=page_start,
            page_end=page_end,
            quote=quote,
            support_type=support_t,  # type: ignore[arg-type]
            score=float(chunk.get("rerank_score", 0.0) or 0.0),
        ))

    used_papers = sorted({r.paper_id for r in refs})
    confidence = compute_confidence(supported=valid_refs, total=valid_refs + len(unsupported))

    return PaperRAGAnswer(
        question=question,
        answer=answer_text or "(LLM 未返回 answer)",
        evidence_refs=refs,
        unsupported_claims=list(unsupported),
        confidence=round(confidence, 4),
        used_papers=used_papers,
        retrieval_mode="llm",  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# fallback
# ---------------------------------------------------------------------------


def fallback_answer(question: str, chunks: list[dict]) -> PaperRAGAnswer:
    """LLM 失败 → fallback: 把检索到的 chunks 整理成 answer.

    retrieval_mode = "fallback", confidence = 0.0
    """

    if not chunks:
        return _no_hit_answer(question, mode="fallback")

    snippets: list[str] = []
    refs: list[EvidenceRef] = []
    for i, c in enumerate(chunks[:5], start=1):
        text = (c.get("text", "") or "")[:300]
        section = c.get("section_title", "Body")
        snippet = f"[{i}] {section}: {text}"
        snippets.append(snippet)
        refs.append(EvidenceRef(
            paper_id=c.get("paper_id", ""),
            chunk_id=c.get("chunk_id", ""),
            page_start=c.get("page_start"),
            page_end=c.get("page_end"),
            quote=text[:200],
            support_type="indirect",
            score=float(c.get("rerank_score", 0.0) or 0.0),
        ))
    answer = (
        "检索到以下相关片段，但未能生成综合回答（LLM 不可用）:\n\n"
        + "\n\n".join(snippets)
    )
    return PaperRAGAnswer(
        question=question,
        answer=answer,
        evidence_refs=refs,
        unsupported_claims=[],
        confidence=0.0,
        used_papers=sorted({r.paper_id for r in refs}),
        retrieval_mode="fallback",  # type: ignore[arg-type]
    )


def _no_hit_answer(question: str, mode: RetrievalMode = "llm") -> PaperRAGAnswer:
    return PaperRAGAnswer(
        question=question,
        answer="未在论文库中找到证据，无法回答该问题。",
        evidence_refs=[],
        unsupported_claims=[],
        confidence=0.0,
        used_papers=[],
        retrieval_mode=mode,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# confidence 计算
# ---------------------------------------------------------------------------


def compute_confidence(supported: int, total: int) -> float:
    """confidence = supported / total, 范围 [0, 1].

    Args:
        supported: 有 chunk 支撑的 claim 数
        total: claim 总数 (supported + unsupported)
    """

    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, supported / total))


# ---------------------------------------------------------------------------
# paper_titles lookup (批量)
# ---------------------------------------------------------------------------


def load_paper_titles(project_id: str, paper_ids: list[str]) -> dict[str, str]:
    """从 storage 读 paper_id → title."""

    out: dict[str, str] = {}
    for pid in paper_ids:
        rec = storage.load_record(project_id, pid)
        if rec:
            out[pid] = rec.title
    return out


# ---------------------------------------------------------------------------
# Session 48 Task 2: RAG answer → Evidence Ledger write-back
# ---------------------------------------------------------------------------


def write_answer_to_ledger(project_id: str, answer: PaperRAGAnswer) -> list[str]:
    """把 PaperRAGAnswer.evidence_refs 写入 Evidence Ledger.

    每条 ref → EvidenceItem(evidence_type=paper_library_chunk, review_status=pending,
    tag=paper_rag). chunk_id 已存在 → 跳过 (RAG 反复命中同一 chunk).

    Returns: list of evidence_id (新建的).
    """

    if not answer.evidence_refs:
        return []
    created: list[str] = []
    for ref in answer.evidence_refs:
        if not ref.chunk_id:
            continue
        # 标题: 优先用 paper_title, 否则用 ref.paper_id
        rec = storage.load_record(project_id, ref.paper_id)
        title = rec.title if rec else f"paper:{ref.paper_id}"
        try:
            resp = ev_store.add_paper_library_chunk(
                project_id,
                paper_id=ref.paper_id,
                chunk_id=ref.chunk_id,
                title=title,
                quote=ref.quote or None,
                page_start=ref.page_start,
                page_end=ref.page_end,
                support_type=ref.support_type,
                review_status="pending",
                url=(rec.url if rec else None),
                arxiv_id=(rec.arxiv_id if rec else None),
                tags=["paper_rag", "paper_library_chunk"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("add_paper_library_chunk failed for %s/%s: %s", ref.paper_id, ref.chunk_id, exc)
            continue
        if resp.ok and resp.evidence_id:
            created.append(resp.evidence_id)
    return created


# ---------------------------------------------------------------------------
# Session 48 Task 6: 引用规则强制 — 在 evidence_refs 上执行 rejected / pending / failed 检查
# ---------------------------------------------------------------------------


def filter_refs_by_citation_rules(
    project_id: str,
    refs: list[EvidenceRef],
) -> tuple[list[EvidenceRef], list[str]]:
    """按 Evidence Ledger 状态 + 引用规则过滤 refs.

    Rules:
    - rejected: 从输出中移除 (citation 规则)
    - pending: 仅保留 support_type=background, 其他降级 / 移除
    - failed verification: 移除 direct/indirect, 仅保留 background
    - 论文库 chunk 不在 ledger 中 → 视为 pending (RAG 刚产生还没写)

    Returns: (filtered_refs, warnings)
    """

    out: list[EvidenceRef] = []
    warnings: list[str] = []
    for ref in refs:
        item = ev_store.find_paper_library_chunk(project_id, ref.paper_id, ref.chunk_id)
        rs = item.review_status if item else "pending"
        vs = item.verification_status if item else "unverified"
        if rs == "rejected":
            warnings.append(
                f"chunk {ref.chunk_id} (paper={ref.paper_id}) rejected → 已移除"
            )
            continue
        if rs == "pending" and ref.support_type == "direct":
            warnings.append(
                f"chunk {ref.chunk_id} (paper={ref.paper_id}) pending → "
                f"direct 降级为 background"
            )
            ref = ref.model_copy(update={"support_type": "background"})
        if vs == "failed" and ref.support_type in ("direct", "indirect"):
            warnings.append(
                f"chunk {ref.chunk_id} (paper={ref.paper_id}) verification failed → "
                f"{ref.support_type} 降级为 background"
            )
            ref = ref.model_copy(update={"support_type": "background"})
        out.append(ref)
    return out, warnings


__all__ = [
    "answer_with_llm",
    "build_context",
    "compute_confidence",
    "fallback_answer",
    "filter_refs_by_citation_rules",
    "load_paper_titles",
    "write_answer_to_ledger",
]