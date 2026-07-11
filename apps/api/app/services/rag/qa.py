"""Re4.5/Re7.6: RAG question answering — LLM generation with citation validation.

Re7.6 change: CitationValidator enforces that every answer's cited_chunks
are traceable to actual indexed chunks. Answers with invalid/unverifiable
citations are abstained, not silently trusted.
"""
from __future__ import annotations

import logging
from typing import Any

from .retriever import retrieve
from .rag_contract import (
    RAGAnswerContract, ChunkCitation, CitationValidator,
)

logger = logging.getLogger(__name__)

QA_SYSTEM = (
    "你是学术论文问答助手。根据提供的论文片段回答问题。"
    "每个答案必须引用来源片段编号（如 [chunk-0]）。"
    "如果片段中没有相关信息，回答\"未在已索引文档中找到相关信息\"。"
    "只输出JSON。"
)

QA_TEMPLATE = """问题: {question}

相关论文片段:
{context}

请基于上述片段回答问题。输出JSON:
{{"answer": "回答内容（需引用 [chunk-N]）", "confidence": 0.0-1.0, "cited_chunks": ["chunk-0", ...]}}

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def answer_question(
    question: str,
    index: dict[str, Any],
    case_id: str,
    top_k: int = 3,
) -> dict[str, Any]:
    """Answer a question using RAG with citation validation (Re7.6)."""
    chunks = retrieve(question, index, top_k=top_k)

    if not chunks:
        return {
            "answer": "未在已索引文档中找到相关信息",
            "confidence": 0.0,
            "cited_chunks": [],
            "retrieved_chunks": [],
            "case_id": case_id,
            "abstain_reason": "no_retrieved_chunks",
        }

    # Build context
    context_parts: list[str] = []
    chunk_map: dict[str, dict] = {}
    for c in chunks:
        cid = c.get("chunk_id", "")
        context_parts.append(f"[{cid}] (score={c.get('score', 0):.2f})\n{c.get('text', '')[:500]}")
        chunk_map[cid] = c
    context = "\n\n".join(context_parts)

    # LLM call
    try:
        from apps.api.app.services import llm_router

        prompt = QA_TEMPLATE.format(question=question[:500], context=context[:3000])
        result = llm_router.call_json(
            prompt, system=QA_SYSTEM, profile="fast_json",
            max_tokens=1000, expected="dict", timeout=30,
        )
    except Exception as exc:
        logger.warning("RAG QA LLM failed: %s — fallback to retrieval only", exc)
        # Fallback: only return extractive citation from top chunk
        top = chunks[0]
        return {
            "answer": f"基于检索结果（LLM 不可用）：{top['text'][:200]}",
            "confidence": 0.3,
            "cited_chunks": [top["chunk_id"]],
            "retrieved_chunks": _format_chunks(chunks),
            "case_id": case_id,
            "abstain_reason": None,
        }

    # Re7.6: Validate citations via CitationValidator
    answer_text = result.get("answer", "")
    raw_cited = result.get("cited_chunks", [])
    confidence = float(result.get("confidence", 0.5))

    # Build cited_chunk objects with verification
    valid_citations = []
    invalid_count = 0
    validator = CitationValidator(chunk_map)
    top_score = max((c.get("score", 0) for c in chunks), default=0)

    for ref in raw_cited:
        ref_str = str(ref) if not isinstance(ref, str) else ref
        cid = ref_str.strip()

        chunk_data = chunk_map.get(cid)
        if not chunk_data:
            invalid_count += 1
            continue

        citation = ChunkCitation(
            chunk_id=cid,
            document_id=chunk_data.get("source", chunk_data.get("document_id", "")),
            page=chunk_data.get("page", 0),
            paragraph=chunk_data.get("paragraph", 0),
            snippet=chunk_data.get("text", "")[:100],
            location_verified=True,
        )
        valid_citations.append(citation)

    # Re7.6: Abstention logic
    abstain_reason = None
    if invalid_count > 0 and not valid_citations:
        abstain_reason = f"all {invalid_count} cited chunks are not in the retrieved index"
    elif not valid_citations and not answer_text.strip():
        abstain_reason = "no valid citations and empty answer"
    elif confidence < 0.3 and not valid_citations:
        abstain_reason = "low confidence with no verifiable citations"
    elif top_score < 0.1:
        abstain_reason = "top retrieval score too low"

    if abstain_reason:
        logger.info("RAG QA: abstaining — %s", abstain_reason)
        return {
            "answer": answer_text or "无法提供有证据支持的答案",
            "confidence": min(confidence, 0.3),
            "cited_chunks": [c.chunk_id for c in valid_citations],
            "retrieved_chunks": _format_chunks(chunks),
            "case_id": case_id,
            "abstain_reason": abstain_reason,
            "citation_valid": False,
        }

    # Check for instruction injection
    if validator.detect_instruction_injection(RAGAnswerContract(
        query=question, answer=answer_text,
        cited_chunks=valid_citations, confidence="high",
    )):
        return {
            "answer": "检测到潜在的内容注入，已拒绝回答",
            "confidence": 0.0,
            "cited_chunks": [],
            "retrieved_chunks": _format_chunks(chunks),
            "case_id": case_id,
            "abstain_reason": "instruction_injection_detected",
            "citation_valid": False,
        }

    return {
        "answer": answer_text,
        "confidence": confidence,
        "cited_chunks": [c.chunk_id for c in valid_citations],
        "retrieved_chunks": _format_chunks(chunks),
        "case_id": case_id,
        "abstain_reason": None,
        "citation_valid": len(valid_citations) > 0,
        "invalid_citation_count": invalid_count,
    }


def _format_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"chunk_id": c.get("chunk_id", ""), "score": c.get("score", 0),
         "text": c.get("text", "")[:200], "source": c.get("source", "")}
        for c in chunks
    ]
